from collections.abc import Generator
from datetime import date, datetime, time, timedelta, timezone
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import EmailOutbox, InAppAlert, Practitioner, Tenant, User
from app.seed import seed_demo
from app.config import settings


@pytest.fixture
def client(tmp_path, monkeypatch) -> Generator[TestClient, None, None]:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    db = TestingSession()
    seed_demo(db)
    db.close()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _auth(client: TestClient, email: str, password: str) -> dict:
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_health(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_register_login_duplicate_and_no_staff_role(client: TestClient):
    r = client.post(
        "/auth/register",
        json={"email": "pat@example.com", "password": "Patient1!", "display_name": "Pat", "role": "doctor"},
    )
    assert r.status_code == 200
    token = r.json()["access_token"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["role"] == "patient"
    assert me.json()["tenant_id"]
    dup = client.post(
        "/auth/register",
        json={"email": "pat@example.com", "password": "Patient1!", "display_name": "Pat"},
    )
    assert dup.status_code == 409
    login = client.post("/auth/login", json={"email": "pat@example.com", "password": "Patient1!"})
    assert login.status_code == 200


def test_me_unauthorized(client: TestClient):
    assert client.get("/auth/me").status_code == 401


def test_staff_login_and_patient_forbidden_hours(client: TestClient):
    doc = _auth(client, "doctor@example.com", "DoctorPass1!")
    ast = _auth(client, "assistant@example.com", "AssistPass1!")
    assert client.get("/auth/me", headers=doc).json()["role"] == "doctor"
    assert client.get("/auth/me", headers=ast).json()["role"] == "assistant"
    client.post(
        "/auth/register",
        json={"email": "p2@example.com", "password": "Patient1!", "display_name": "P2"},
    )
    pat = _auth(client, "p2@example.com", "Patient1!")
    practitioners = client.get("/practitioners", headers=doc).json()
    pid = practitioners[0]["id"]
    denied = client.post(
        "/hours",
        headers=pat,
        json={"practitioner_id": pid, "weekday": 0, "start_time": "09:00:00", "end_time": "12:00:00"},
    )
    assert denied.status_code == 403
    ok = client.post(
        "/hours",
        headers=ast,
        json={"practitioner_id": pid, "weekday": 0, "start_time": "09:00:00", "end_time": "12:00:00"},
    )
    assert ok.status_code == 200


def _future_monday() -> date:
    d = date.today() + timedelta(days=14)
    return d + timedelta(days=(0 - d.weekday()) % 7)


def test_availability_closed_date_and_taken_slot(client: TestClient):
    doc = _auth(client, "doctor@example.com", "DoctorPass1!")
    pid = client.get("/practitioners", headers=doc).json()[0]["id"]
    day = _future_monday()
    client.post(
        "/hours",
        headers=doc,
        json={"practitioner_id": pid, "weekday": 0, "start_time": "09:00:00", "end_time": "10:00:00"},
    )
    slots = client.get(f"/practitioners/{pid}/availability", params={"date": day.isoformat()}, headers=doc)
    assert slots.status_code == 200
    assert len(slots.json()) == 2
    client.post(
        "/exceptions",
        headers=doc,
        json={"practitioner_id": pid, "closed_on": day.isoformat(), "reason": "leave"},
    )
    closed = client.get(f"/practitioners/{pid}/availability", params={"date": day.isoformat()}, headers=doc)
    assert closed.json() == []


def test_available_dates_only_lists_days_with_open_slots(client: TestClient):
    doc = _auth(client, "doctor@example.com", "DoctorPass1!")
    pid = client.get("/practitioners", headers=doc).json()[0]["id"]
    day = _future_monday()
    client.post(
        "/hours",
        headers=doc,
        json={"practitioner_id": pid, "weekday": 0, "start_time": "09:00:00", "end_time": "10:00:00"},
    )
    start = day
    end = day + timedelta(days=6)
    r = client.get(
        f"/practitioners/{pid}/available-dates",
        params={"start": start.isoformat(), "end": end.isoformat()},
        headers=doc,
    )
    assert r.status_code == 200, r.text
    assert r.json() == [day.isoformat()]
    too_wide = client.get(
        f"/practitioners/{pid}/available-dates",
        params={"start": start.isoformat(), "end": (start + timedelta(days=63)).isoformat()},
        headers=doc,
    )
    assert too_wide.status_code == 400


def test_availability_is_deduped_sorted_and_excludes_past(client: TestClient):
    doc = _auth(client, "doctor@example.com", "DoctorPass1!")
    client.post(
        "/auth/register",
        json={"email": "slots@example.com", "password": "Patient1!", "display_name": "Slots"},
    )
    pat = _auth(client, "slots@example.com", "Patient1!")
    pid = client.get("/practitioners", headers=doc).json()[0]["id"]
    day = _future_monday()
    for hours in (("09:00:00", "10:00:00"), ("09:00:00", "10:30:00")):
        client.post(
            "/hours",
            headers=doc,
            json={"practitioner_id": pid, "weekday": 0, "start_time": hours[0], "end_time": hours[1]},
        )
    rows = client.get(
        f"/practitioners/{pid}/availability", params={"date": day.isoformat()}, headers=pat
    ).json()
    starts = [r["starts_at"] for r in rows]
    assert starts == sorted(starts)
    assert len(starts) == len(set(starts))
    assert len(starts) == 3

    past_day = date.today() - timedelta(days=7)
    client.post(
        "/hours",
        headers=doc,
        json={
            "practitioner_id": pid,
            "weekday": past_day.weekday(),
            "start_time": "09:00:00",
            "end_time": "10:00:00",
        },
    )
    past = client.get(
        f"/practitioners/{pid}/availability", params={"date": past_day.isoformat()}, headers=pat
    ).json()
    assert past == []


def test_booking_conflict_on_behalf_cancel_alerts_and_docs(client: TestClient):
    doc = _auth(client, "doctor@example.com", "DoctorPass1!")
    ast = _auth(client, "assistant@example.com", "AssistPass1!")
    pid = client.get("/practitioners", headers=doc).json()[0]["id"]
    day = _future_monday()
    client.post(
        "/hours",
        headers=doc,
        json={"practitioner_id": pid, "weekday": 0, "start_time": "09:00:00", "end_time": "12:00:00"},
    )
    r = client.post(
        "/auth/register",
        json={"email": "book@example.com", "password": "Patient1!", "display_name": "Booker"},
    )
    pat = {"Authorization": f"Bearer {r.json()['access_token']}"}
    other = client.post(
        "/auth/register",
        json={"email": "other@example.com", "password": "Patient1!", "display_name": "Other"},
    )
    other_h = {"Authorization": f"Bearer {other.json()['access_token']}"}
    slots = client.get(f"/practitioners/{pid}/availability", params={"date": day.isoformat()}, headers=pat).json()
    starts = slots[0]["starts_at"]
    first = client.post("/bookings", headers=pat, json={"practitioner_id": pid, "starts_at": starts})
    assert first.status_code == 200, first.text
    assert first.json()["visit_record_id"]
    second = client.post("/bookings", headers=pat, json={"practitioner_id": pid, "starts_at": starts})
    assert second.status_code == 409
    left = client.get(f"/practitioners/{pid}/availability", params={"date": day.isoformat()}, headers=pat).json()
    assert starts not in [s["starts_at"] for s in left]

    on_behalf_denied = client.post(
        "/bookings/on-behalf",
        headers=pat,
        json={"patient_id": 1, "practitioner_id": pid, "starts_at": slots[1]["starts_at"]},
    )
    assert on_behalf_denied.status_code == 403

    patients = client.get("/patients", headers=ast).json()
    patient_id = next(p["id"] for p in patients if p["email"] == "other@example.com")
    staff_book = client.post(
        "/bookings/on-behalf",
        headers=ast,
        json={"patient_id": patient_id, "practitioner_id": pid, "starts_at": slots[1]["starts_at"]},
    )
    assert staff_book.status_code == 200, staff_book.text

    visit_id = first.json()["visit_record_id"]
    other_get = client.get(f"/visits/{visit_id}", headers=other_h)
    assert other_get.status_code == 404

    upd = client.patch(f"/visits/{visit_id}", headers=pat, json={"notes": "sore throat"})
    assert upd.status_code == 200
    assert upd.json()["updated_by_user_id"]

    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
    up = client.post(
        f"/visits/{visit_id}/documents",
        headers=pat,
        files={"file": ("lab.png", BytesIO(png), "image/png")},
    )
    assert up.status_code == 200, up.text
    bad = client.post(
        f"/visits/{visit_id}/documents",
        headers=pat,
        files={"file": ("x.exe", BytesIO(b"MZ"), "application/octet-stream")},
    )
    assert bad.status_code == 400

    dl = client.get(f"/visits/{visit_id}/documents/{up.json()['id']}", headers=pat)
    assert dl.status_code == 200
    noauth = client.get(f"/visits/{visit_id}/documents/{up.json()['id']}")
    assert noauth.status_code == 401

    cancel = client.post(f"/bookings/{first.json()['id']}/cancel", headers=pat, json={"reason": "sick"})
    assert cancel.status_code == 200
    assert cancel.json()["cancelled_by_user_id"]
    again = client.post(f"/bookings/{first.json()['id']}/cancel", headers=pat, json={})
    assert again.status_code == 409
    freed = client.get(f"/practitioners/{pid}/availability", params={"date": day.isoformat()}, headers=pat).json()
    assert starts in [s["starts_at"] for s in freed]

    alerts = client.get("/alerts", headers=pat).json()
    assert any(a["event_type"] == "booking.created" for a in alerts)
    unread_id = alerts[0]["id"]
    client.post(f"/alerts/{unread_id}/read", headers=pat)
    after = client.get("/alerts", headers=pat).json()
    found = next(a for a in after if a["id"] == unread_id)
    assert found["read_at"]

    doc_alerts = client.get("/alerts", headers=doc).json()
    assert len(doc_alerts) >= 1
    other_alerts = client.get("/alerts", headers=other_h).json()
    assert all(a["id"] != unread_id for a in other_alerts)
