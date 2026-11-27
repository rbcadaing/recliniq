"""Doctor sign-up and email verification through the HTTP API, against real PostgreSQL.

Requests share the test's rolled-back session, so nothing persists. The mailer is in-memory;
the rate limiter commits in its own transaction, so its (exempt) table is cleared per test.
"""

import logging
import re
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.infrastructure.accounts.mailer import InMemoryMailer, SmtpMailer
from app.infrastructure.accounts.models import (
    DoctorProfileModel,
    EmailVerificationTokenModel,
    UserModel,
)
from app.presentation.dependencies import get_clock, get_mailer, get_session

SIGNUP = "/api/v1/auth/doctors/signup"
CONFIRM = "/api/v1/auth/email-verification/confirm"
RESEND = "/api/v1/auth/email-verification/resend"
PASSWORD = "correct horse battery staple"
TOKEN_IN_LINK = re.compile(r"verify-email\?token=([\w-]+)")


class FakeClock:
    def __init__(self) -> None:
        self.current = datetime.now(UTC)

    def now(self) -> datetime:
        return self.current


@pytest.fixture
async def clean_rate_limits(engine: AsyncEngine) -> AsyncIterator[None]:
    async with engine.begin() as connection:
        await connection.execute(text("DELETE FROM rate_limit_counters"))
    yield
    async with engine.begin() as connection:
        await connection.execute(text("DELETE FROM rate_limit_counters"))


@pytest.fixture
def mailer() -> InMemoryMailer:
    return InMemoryMailer()


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
async def api(
    integration_app: FastAPI,
    db_session: AsyncSession,
    mailer: InMemoryMailer,
    clock: FakeClock,
    clean_rate_limits: None,
) -> AsyncIterator[Callable[..., AsyncClient]]:
    async def shared_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    integration_app.dependency_overrides[get_session] = shared_session
    integration_app.dependency_overrides[get_mailer] = lambda: mailer
    integration_app.dependency_overrides[get_clock] = lambda: clock
    clients: list[AsyncClient] = []

    def make(ip: str = "203.0.113.10") -> AsyncClient:
        transport = ASGITransport(app=integration_app, client=(ip, 50000))
        client = AsyncClient(transport=transport, base_url="http://testserver")
        clients.append(client)
        return client

    async with integration_app.router.lifespan_context(integration_app):
        yield make
        for client in clients:
            await client.aclose()


@pytest.fixture
async def client(api: Callable[..., AsyncClient]) -> AsyncClient:
    return api()


@pytest.fixture
async def specialization_id(client: AsyncClient) -> str:
    response = await client.get("/api/v1/specializations")
    return str(response.json()[0]["id"])


@pytest.fixture
def signup(specialization_id: str) -> Callable[..., dict[str, Any]]:
    def build(**overrides: Any) -> dict[str, Any]:
        body: dict[str, Any] = {
            "first_name": "Juan",
            "middle_name": "Santos",
            "last_name": "Dela Cruz",
            "email": "Juan.DelaCruz@Example.com",
            "mobile": "0917 123 4567",
            "password": PASSWORD,
            "specialization_id": specialization_id,
            "prc_license_no": "12345",
            "privacy_consent": True,
        }
        body.update(overrides)
        return body

    return build


def token_from(mailer: InMemoryMailer, index: int = -1) -> str:
    match = TOKEN_IN_LINK.search(mailer.outbox[index].text)
    assert match is not None
    return match.group(1)


async def user_row(session: AsyncSession, email: str = "juan.delacruz@example.com") -> UserModel:
    row = await session.scalar(select(UserModel).where(UserModel.email == email))
    assert row is not None
    return row


def field_errors(response: Any) -> set[str]:
    return {d["field"].split(".")[-1] for d in response.json()["error"]["details"]}


# --- Specializations --------------------------------------------------------------------


async def test_specializations_public_and_sorted(client: AsyncClient) -> None:
    response = await client.get("/api/v1/specializations")
    assert response.status_code == 200
    items = response.json()
    assert items
    assert [i["name"] for i in items] == sorted(i["name"] for i in items)
    assert set(items[0]) == {"id", "code", "name"}


# --- Sign-up ----------------------------------------------------------------------------


async def test_successful_sign_up(
    client: AsyncClient,
    signup: Callable[..., dict[str, Any]],
    db_session: AsyncSession,
    mailer: InMemoryMailer,
    clock: FakeClock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.DEBUG):
        response = await client.post(SIGNUP, json=signup())

    assert response.status_code == 202
    assert response.json() == {"message": "Check your email for a link to verify your account."}

    user = await user_row(db_session)
    assert user.role == "doctor"
    assert user.mobile == "+639171234567"
    assert user.middle_name == "Santos"
    assert user.email_verified_at is None
    assert user.privacy_consent_at == clock.current
    assert user.privacy_notice_version == "2026-11-draft"
    assert user.password_hash.startswith("$argon2id$")
    assert PASSWORD not in user.password_hash
    assert caplog.records  # the request was logged (access log, email) ...
    assert all(PASSWORD not in str(r.msg) for r in caplog.records)  # ... without the password
    assert PASSWORD not in caplog.text

    profile = await db_session.get(DoctorProfileModel, user.id)
    assert profile is not None
    assert profile.prc_license_no == "0012345"
    assert profile.license_status == "pending"

    (email,) = mailer.outbox
    assert email.to == "juan.delacruz@example.com"
    assert "http://localhost:5173/verify-email?token=" in email.text


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"first_name": ""}, "first_name"),
        ({"email": "not-an-email"}, "email"),
        ({"mobile": "+14155550100"}, "mobile"),
        ({"mobile": "0917123"}, "mobile"),
        ({"prc_license_no": "AB12345"}, "prc_license_no"),
        ({"prc_license_no": "12345678"}, "prc_license_no"),
        ({"password": "a" * 11}, "password"),
        ({"password": "password1234"}, "password"),
        ({"privacy_consent": False}, "privacy_consent"),
        ({"specialization_id": "00000000-0000-0000-0000-000000000000"}, "specialization_id"),
    ],
)
async def test_invalid_field_returns_422_and_creates_nothing(
    client: AsyncClient,
    signup: Callable[..., dict[str, Any]],
    db_session: AsyncSession,
    mailer: InMemoryMailer,
    overrides: dict[str, Any],
    field: str,
) -> None:
    response = await client.post(SIGNUP, json=signup(**overrides))

    assert response.status_code == 422
    assert field in field_errors(response)
    assert PASSWORD not in response.text
    assert await db_session.scalar(select(UserModel)) is None
    assert mailer.outbox == []


async def test_missing_field_returns_422(
    client: AsyncClient, signup: Callable[..., dict[str, Any]]
) -> None:
    body = signup()
    del body["prc_license_no"]
    response = await client.post(SIGNUP, json=body)
    assert response.status_code == 422
    assert "prc_license_no" in field_errors(response)


@pytest.mark.parametrize(
    ("overrides", "field"),
    [({"prc_license_no": "7654321"}, "mobile"), ({"mobile": "09180000000"}, "prc_license_no")],
)
async def test_mobile_or_prc_conflict_returns_409(
    client: AsyncClient,
    signup: Callable[..., dict[str, Any]],
    overrides: dict[str, Any],
    field: str,
) -> None:
    assert (await client.post(SIGNUP, json=signup())).status_code == 202

    response = await client.post(SIGNUP, json=signup(email="other@example.com", **overrides))

    assert response.status_code == 409
    assert response.json()["error"]["details"] == {"field": field}


async def test_registered_emails_get_identical_responses(
    client: AsyncClient,
    signup: Callable[..., dict[str, Any]],
    db_session: AsyncSession,
    mailer: InMemoryMailer,
) -> None:
    new = await client.post(SIGNUP, json=signup())
    other = {"mobile": "09180000000", "prc_license_no": "7654321"}

    unverified = await client.post(SIGNUP, json=signup(**other))
    assert "verify-email?token=" in mailer.outbox[-1].text  # a fresh link for the owner

    user = await user_row(db_session)
    user.email_verified_at = datetime.now(UTC)
    await db_session.flush()
    verified = await client.post(SIGNUP, json=signup(**other))
    assert "already have" in mailer.outbox[-1].subject

    assert new.status_code == unverified.status_code == verified.status_code == 202
    assert new.json() == unverified.json() == verified.json()
    users = (await db_session.scalars(select(UserModel))).all()
    assert len(users) == 1


async def test_soft_deleted_account_does_not_block_sign_up(
    client: AsyncClient, signup: Callable[..., dict[str, Any]], db_session: AsyncSession
) -> None:
    assert (await client.post(SIGNUP, json=signup())).status_code == 202
    user = await user_row(db_session)
    profile = await db_session.get(DoctorProfileModel, user.id)
    assert profile is not None
    user.deleted_at = profile.deleted_at = datetime.now(UTC)
    await db_session.flush()

    response = await client.post(SIGNUP, json=signup())

    assert response.status_code == 202
    assert (await user_row(db_session)).id != user.id


async def test_sign_up_rate_limited_per_ip(
    client: AsyncClient, signup: Callable[..., dict[str, Any]]
) -> None:
    for i in range(5):
        body = signup(email=f"d{i}@example.com", mobile=f"0917000000{i}", prc_license_no=str(i))
        assert (await client.post(SIGNUP, json=body)).status_code == 202

    response = await client.post(SIGNUP, json=signup(email="d9@example.com"))

    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0
    assert response.json()["error"]["code"] == "too_many_requests"


async def test_sign_up_rate_limited_per_email_across_ips(
    api: Callable[..., AsyncClient], signup: Callable[..., dict[str, Any]]
) -> None:
    for i in range(3):
        body = signup(mobile=f"0917000000{i}", prc_license_no=str(i))
        assert (await api(f"10.0.0.{i}").post(SIGNUP, json=body)).status_code == 202

    response = await api("10.0.0.99").post(SIGNUP, json=signup())
    assert response.status_code == 429


async def test_mail_failure_still_returns_202(
    integration_app: FastAPI,
    client: AsyncClient,
    signup: Callable[..., dict[str, Any]],
    db_session: AsyncSession,
    caplog: pytest.LogCaptureFixture,
) -> None:
    unreachable = SmtpMailer(host="127.0.0.1", port=1, sender="x@recliniq.local", timeout_seconds=2)
    integration_app.dependency_overrides[get_mailer] = lambda: unreachable

    with caplog.at_level(logging.INFO, logger="app.mail"):
        response = await client.post(SIGNUP, json=signup())

    assert response.status_code == 202
    assert await user_row(db_session)
    failures = [
        r.msg
        for r in caplog.records
        if isinstance(r.msg, dict) and r.msg.get("event") == "email_send_failed"
    ]
    assert len(failures) == 1
    assert failures[0]["to"] == "j***@example.com"


# --- Confirm and resend -----------------------------------------------------------------


async def test_confirm_valid_then_reused(
    client: AsyncClient,
    signup: Callable[..., dict[str, Any]],
    db_session: AsyncSession,
    mailer: InMemoryMailer,
) -> None:
    await client.post(SIGNUP, json=signup())
    token = token_from(mailer)

    response = await client.post(CONFIRM, json={"token": token})

    assert response.status_code == 200
    user = await user_row(db_session)
    await db_session.refresh(user)
    assert user.email_verified_at is not None
    stored = await db_session.scalar(select(EmailVerificationTokenModel))
    assert stored is not None
    assert stored.token_hash != token

    reused = await client.post(CONFIRM, json={"token": token})
    assert reused.status_code == 400
    assert reused.json()["error"]["code"] == "invalid_token"


async def test_confirm_expired_and_unknown(
    client: AsyncClient,
    signup: Callable[..., dict[str, Any]],
    db_session: AsyncSession,
    mailer: InMemoryMailer,
    clock: FakeClock,
) -> None:
    await client.post(SIGNUP, json=signup())
    clock.current += timedelta(hours=24, seconds=1)

    expired = await client.post(CONFIRM, json={"token": token_from(mailer)})
    unknown = await client.post(CONFIRM, json={"token": "never-issued"})

    assert expired.status_code == 400
    assert expired.json()["error"]["code"] == "token_expired"
    assert unknown.status_code == 400
    assert unknown.json()["error"]["code"] == "invalid_token"
    assert (await user_row(db_session)).email_verified_at is None


async def test_resend_invalidates_old_link(
    client: AsyncClient, signup: Callable[..., dict[str, Any]], mailer: InMemoryMailer
) -> None:
    await client.post(SIGNUP, json=signup())
    old = token_from(mailer)

    response = await client.post(RESEND, json={"email": "juan.delacruz@example.com"})

    assert response.status_code == 202
    new = token_from(mailer)
    assert new != old
    assert (await client.post(CONFIRM, json={"token": old})).status_code == 400
    assert (await client.post(CONFIRM, json={"token": new})).status_code == 200


async def test_resend_identical_for_unknown_and_verified(
    client: AsyncClient, signup: Callable[..., dict[str, Any]], mailer: InMemoryMailer
) -> None:
    await client.post(SIGNUP, json=signup())
    await client.post(CONFIRM, json={"token": token_from(mailer)})
    sent_before = len(mailer.outbox)

    verified = await client.post(RESEND, json={"email": "juan.delacruz@example.com"})
    unknown = await client.post(RESEND, json={"email": "nobody@example.com"})

    assert verified.status_code == unknown.status_code == 202
    assert verified.json() == unknown.json()
    assert len(mailer.outbox) == sent_before


async def test_resend_rate_limited(client: AsyncClient, mailer: InMemoryMailer) -> None:
    for _ in range(3):
        assert (await client.post(RESEND, json={"email": "a@example.com"})).status_code == 202

    response = await client.post(RESEND, json={"email": "a@example.com"})

    assert response.status_code == 429
    assert "Retry-After" in response.headers
