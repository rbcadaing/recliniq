"""Login, refresh, logout, /me, and password reset through the HTTP API (real PostgreSQL)."""

import re
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.infrastructure.accounts.mailer import InMemoryMailer
from app.infrastructure.accounts.models import (
    DoctorProfileModel,
    EmailVerificationTokenModel,
    PasswordResetTokenModel,
    RefreshTokenModel,
    UserModel,
)
from app.presentation.dependencies import get_mailer
from tests.integration.api_support import CONFIRM, PASSWORD, SIGNUP, FakeClock, token_from

LOGIN = "/api/v1/auth/login"
REFRESH = "/api/v1/auth/refresh"
LOGOUT = "/api/v1/auth/logout"
FORGOT = "/api/v1/auth/password/forgot"
RESET = "/api/v1/auth/password/reset"
ME = "/api/v1/me"
EMAIL = "juan.delacruz@example.com"
NEW_PASSWORD = "brand new passphrase for juan"
RESET_LINK = re.compile(r"reset-password\?token=([\w-]+)")


async def verified_doctor(
    client: AsyncClient, signup: Callable[..., dict[str, Any]], mailer: InMemoryMailer
) -> None:
    assert (await client.post(SIGNUP, json=signup())).status_code == 202
    assert (await client.post(CONFIRM, json={"token": token_from(mailer)})).status_code == 200


async def login(client: AsyncClient, email: str = EMAIL, password: str = PASSWORD) -> Any:
    return await client.post(LOGIN, json={"email": email, "password": password})


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def reset_token(mailer: InMemoryMailer) -> str:
    match = RESET_LINK.search(mailer.outbox[-1].text)
    assert match is not None
    return match.group(1)


# --- Login ------------------------------------------------------------------------------


async def test_login_success_case_insensitive(
    client: AsyncClient, signup: Callable[..., dict[str, Any]], mailer: InMemoryMailer
) -> None:
    await verified_doctor(client, signup, mailer)

    response = await login(client, email="Juan.DelaCruz@EXAMPLE.com")

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 900
    assert body["refresh_expires_in"] == 30 * 24 * 3600
    assert body["access_token"]
    assert body["refresh_token"]
    assert response.headers["Cache-Control"] == "no-store"


async def test_wrong_password_and_unknown_email_identical(
    client: AsyncClient, signup: Callable[..., dict[str, Any]], mailer: InMemoryMailer
) -> None:
    await verified_doctor(client, signup, mailer)

    wrong = await login(client, password="wrong password entirely")
    unknown = await login(client, email="nobody@example.com")

    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["error"]["code"] == unknown.json()["error"]["code"] == "invalid_credentials"
    assert wrong.json()["error"]["message"] == unknown.json()["error"]["message"]


async def test_unverified_email(client: AsyncClient, signup: Callable[..., dict[str, Any]]) -> None:
    assert (await client.post(SIGNUP, json=signup())).status_code == 202

    right = await login(client)
    wrong = await login(client, password="wrong password entirely")

    assert right.status_code == 403
    assert right.json()["error"]["code"] == "email_not_verified"
    assert "access_token" not in right.text
    assert wrong.status_code == 401


async def test_login_rate_limited_per_email(
    api: Callable[..., AsyncClient],
    signup: Callable[..., dict[str, Any]],
    mailer: InMemoryMailer,
) -> None:
    client = api()
    await verified_doctor(client, signup, mailer)
    for i in range(10):
        await login(api(f"10.1.0.{i}"), password="wrong password entirely")

    response = await login(api("10.1.0.99"))  # correct password, other IP

    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0


# --- /me and the bearer dependency ------------------------------------------------------


async def test_me_for_pending_doctor(
    client: AsyncClient, signup: Callable[..., dict[str, Any]], mailer: InMemoryMailer
) -> None:
    await verified_doctor(client, signup, mailer)
    access = (await login(client)).json()["access_token"]

    response = await client.get(ME, headers=bearer(access))

    assert response.status_code == 200
    me = response.json()
    assert me["email"] == EMAIL
    assert me["role"] == "doctor"
    assert me["email_verified"] is True
    assert me["doctor"]["license_status"] == "pending"
    assert me["doctor"]["specialization"]["name"]


@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": "Bearer not-a-jwt"}, {"Authorization": "Basic dXNlcjpwYXNz"}],
    ids=["missing", "garbage", "wrong-scheme"],
)
async def test_me_requires_valid_token(client: AsyncClient, headers: dict[str, str]) -> None:
    response = await client.get(ME, headers=headers)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json()["error"]["code"] == "not_authenticated"


async def test_expired_token_rejected(
    client: AsyncClient,
    signup: Callable[..., dict[str, Any]],
    mailer: InMemoryMailer,
    clock: FakeClock,
) -> None:
    await verified_doctor(client, signup, mailer)
    clock.current = datetime.now(UTC) - timedelta(minutes=20)
    access = (await login(client)).json()["access_token"]
    clock.current = datetime.now(UTC)

    assert (await client.get(ME, headers=bearer(access))).status_code == 401


async def test_deleted_account_token_rejected(
    client: AsyncClient,
    signup: Callable[..., dict[str, Any]],
    mailer: InMemoryMailer,
    db_session: AsyncSession,
) -> None:
    await verified_doctor(client, signup, mailer)
    access = (await login(client)).json()["access_token"]
    user = await db_session.scalar(select(UserModel).where(UserModel.email == EMAIL))
    assert user is not None
    user.deleted_at = datetime.now(UTC)
    await db_session.flush()

    assert (await client.get(ME, headers=bearer(access))).status_code == 401


# --- Refresh and logout -----------------------------------------------------------------


async def test_refresh_rotates_and_reuse_revokes_session(
    client: AsyncClient, signup: Callable[..., dict[str, Any]], mailer: InMemoryMailer
) -> None:
    await verified_doctor(client, signup, mailer)
    first = (await login(client)).json()

    rotated = await client.post(REFRESH, json={"refresh_token": first["refresh_token"]})
    assert rotated.status_code == 200
    second = rotated.json()
    assert second["refresh_token"] != first["refresh_token"]
    assert (await client.get(ME, headers=bearer(second["access_token"]))).status_code == 200

    replay = await client.post(REFRESH, json={"refresh_token": first["refresh_token"]})
    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "invalid_refresh_token"
    # The newest token of the same session died too.
    newest = await client.post(REFRESH, json={"refresh_token": second["refresh_token"]})
    assert newest.status_code == 401


async def test_unknown_refresh_token(client: AsyncClient) -> None:
    response = await client.post(REFRESH, json={"refresh_token": "never-issued"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_refresh_token"


async def test_logout_revokes_and_is_idempotent(
    client: AsyncClient, signup: Callable[..., dict[str, Any]], mailer: InMemoryMailer
) -> None:
    await verified_doctor(client, signup, mailer)
    tokens = (await login(client)).json()

    first = await client.post(LOGOUT, json={"refresh_token": tokens["refresh_token"]})
    again = await client.post(LOGOUT, json={"refresh_token": tokens["refresh_token"]})
    unknown = await client.post(LOGOUT, json={"refresh_token": "never-issued"})

    assert first.status_code == again.status_code == unknown.status_code == 204
    refreshed = await client.post(REFRESH, json={"refresh_token": tokens["refresh_token"]})
    assert refreshed.status_code == 401


# --- Password reset ---------------------------------------------------------------------


async def test_forgot_password_identical_responses(
    client: AsyncClient, signup: Callable[..., dict[str, Any]], mailer: InMemoryMailer
) -> None:
    await verified_doctor(client, signup, mailer)
    sent = len(mailer.outbox)

    known = await client.post(FORGOT, json={"email": EMAIL})
    unknown = await client.post(FORGOT, json={"email": "nobody@example.com"})

    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert len(mailer.outbox) == sent + 1
    assert "reset-password?token=" in mailer.outbox[-1].text


async def test_reset_flow_end_to_end(
    client: AsyncClient,
    signup: Callable[..., dict[str, Any]],
    mailer: InMemoryMailer,
    db_session: AsyncSession,
) -> None:
    await verified_doctor(client, signup, mailer)
    other_device = (await login(client)).json()
    await client.post(FORGOT, json={"email": EMAIL})
    token = reset_token(mailer)

    weak = await client.post(RESET, json={"token": token, "new_password": "password1234"})
    assert weak.status_code == 422
    assert "new_password" in weak.text

    done = await client.post(RESET, json={"token": token, "new_password": NEW_PASSWORD})
    assert done.status_code == 200  # the token survived the 422 above

    assert (await login(client)).status_code == 401
    assert (await login(client, password=NEW_PASSWORD)).status_code == 200
    stale = await client.post(REFRESH, json={"refresh_token": other_device["refresh_token"]})
    assert stale.status_code == 401  # signed out everywhere

    reused = await client.post(RESET, json={"token": token, "new_password": NEW_PASSWORD + "!"})
    assert reused.status_code == 400
    assert reused.json()["error"]["code"] == "invalid_token"


async def test_reset_verifies_unverified_email(
    client: AsyncClient,
    signup: Callable[..., dict[str, Any]],
    mailer: InMemoryMailer,
) -> None:
    assert (await client.post(SIGNUP, json=signup())).status_code == 202
    await client.post(FORGOT, json={"email": EMAIL})

    await client.post(RESET, json={"token": reset_token(mailer), "new_password": NEW_PASSWORD})

    assert (await login(client, password=NEW_PASSWORD)).status_code == 200


async def test_reset_expired_link(
    client: AsyncClient,
    signup: Callable[..., dict[str, Any]],
    mailer: InMemoryMailer,
    clock: FakeClock,
) -> None:
    await verified_doctor(client, signup, mailer)
    await client.post(FORGOT, json={"email": EMAIL})
    clock.current += timedelta(minutes=61)

    response = await client.post(
        RESET, json={"token": reset_token(mailer), "new_password": NEW_PASSWORD}
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "token_expired"


async def test_forgot_password_rate_limited(client: AsyncClient) -> None:
    for _ in range(3):
        assert (await client.post(FORGOT, json={"email": "a@example.com"})).status_code == 202

    response = await client.post(FORGOT, json={"email": "a@example.com"})

    assert response.status_code == 429
    assert "Retry-After" in response.headers


# --- Real unit of work: reuse revocation must be committed -------------------------------


@pytest_asyncio.fixture
async def committed_app(
    integration_app: FastAPI, engine: AsyncEngine, clean_rate_limits: None
) -> AsyncIterator[tuple[AsyncClient, InMemoryMailer, str]]:
    """The app with its REAL session handling (commit on success, rollback on error).

    Data is committed, so the fixture removes it afterwards with the maintenance override.
    """
    mailer = InMemoryMailer()
    integration_app.dependency_overrides[get_mailer] = lambda: mailer
    email = f"uow-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=integration_app, client=("203.0.113.50", 50000))
    async with (
        integration_app.router.lifespan_context(integration_app),
        AsyncClient(transport=transport, base_url="http://testserver") as client,
    ):
        yield client, mailer, email
    async with engine.begin() as connection:
        await connection.execute(text("SET LOCAL recliniq.allow_hard_delete = 'on'"))
        user_ids = select(UserModel.id).where(UserModel.email == email).scalar_subquery()
        for model in (
            RefreshTokenModel,
            EmailVerificationTokenModel,
            PasswordResetTokenModel,
            DoctorProfileModel,
        ):
            await connection.execute(model.__table__.delete().where(model.user_id.in_(user_ids)))
        await connection.execute(UserModel.__table__.delete().where(UserModel.email == email))


async def test_reuse_revocation_survives_the_401(
    committed_app: tuple[AsyncClient, InMemoryMailer, str],
) -> None:
    # No `signup`/`client` fixtures here: they install the shared-session override.
    client, mailer, email = committed_app
    specialization_id = (await client.get("/api/v1/specializations")).json()[0]["id"]
    body = {
        "first_name": "Uow",
        "last_name": "Test",
        "email": email,
        "mobile": "0999 000 1111",
        "password": PASSWORD,
        "specialization_id": specialization_id,
        "prc_license_no": "7777777",
        "privacy_consent": True,
    }
    assert (await client.post(SIGNUP, json=body)).status_code == 202
    assert (await client.post(CONFIRM, json={"token": token_from(mailer)})).status_code == 200
    first = (await login(client, email=email)).json()
    second = (await client.post(REFRESH, json={"refresh_token": first["refresh_token"]})).json()

    replay = await client.post(REFRESH, json={"refresh_token": first["refresh_token"]})
    assert replay.status_code == 401

    # A new request (new unit of work): the revocation was committed, so the newest token is dead.
    newest = await client.post(REFRESH, json={"refresh_token": second["refresh_token"]})
    assert newest.status_code == 401
