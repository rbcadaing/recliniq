import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt as pyjwt
import pytest
from argon2 import PasswordHasher as Argon2

from app.application.accounts.emails import (
    account_exists_email,
    password_reset_email,
    password_reset_link,
    verification_email,
    verification_link,
)
from app.application.accounts.ports import EmailMessage
from app.domain.accounts.entities import User
from app.domain.accounts.values import Role
from app.domain.errors import NotAuthenticatedError
from app.infrastructure.accounts import mailer as mailer_module
from app.infrastructure.accounts.hasher import Argon2PasswordHasher
from app.infrastructure.accounts.jwt import JwtTokenIssuer
from app.infrastructure.accounts.mailer import SmtpMailer, mask_email

PASSWORD = "correct horse battery staple"

# --- Password hasher --------------------------------------------------------------------


async def test_hash_verifies_and_hides_password() -> None:
    hasher = Argon2PasswordHasher()
    first = await hasher.hash(PASSWORD)
    second = await hasher.hash(PASSWORD)

    assert first.startswith("$argon2id$")
    assert PASSWORD not in first
    assert first != second  # random salt
    assert await hasher.verify(first, PASSWORD)
    assert not await hasher.verify(first, "wrong horse battery staple")
    assert not await hasher.verify("not-a-hash", PASSWORD)


# --- Templates --------------------------------------------------------------------------


def test_verification_link_format() -> None:
    link = verification_link("http://localhost:5173/", "abc-_123")
    assert link == "http://localhost:5173/verify-email?token=abc-_123"


def test_verification_email_contains_link_and_escapes_name() -> None:
    message = verification_email(
        to="doc@example.com",
        first_name="<Juan>",
        link="http://localhost:5173/verify-email?token=t0k",
        ttl_hours=24,
        app_name="RecliniQ",
    )
    assert message.to == "doc@example.com"
    assert "http://localhost:5173/verify-email?token=t0k" in message.text
    assert 'href="http://localhost:5173/verify-email?token=t0k"' in message.html
    assert "&lt;Juan&gt;" in message.html
    assert "24 hours" in message.text


def test_account_exists_email() -> None:
    message = account_exists_email(to="doc@example.com", first_name="Juan", app_name="RecliniQ")
    assert "already have" in message.subject
    assert "reset your password" in message.text


# --- SMTP mailer ------------------------------------------------------------------------

MESSAGE = EmailMessage(
    to="juan@example.com",
    subject="Verify your RecliniQ email",
    text="secret-token-123",
    html="<p>secret-token-123</p>",
)


def test_mask_email() -> None:
    assert mask_email("juan@example.com") == "j***@example.com"
    assert mask_email("nonsense") == "***"


def mail_events(caplog: pytest.LogCaptureFixture) -> list[dict[str, Any]]:
    return [r.msg for r in caplog.records if r.name == "app.mail" and isinstance(r.msg, dict)]


async def test_smtp_mailer_sends_multipart(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    sent: dict[str, Any] = {}

    async def fake_send(message: Any, **kwargs: Any) -> None:
        sent["message"] = message
        sent.update(kwargs)

    monkeypatch.setattr(mailer_module.aiosmtplib, "send", fake_send)
    mailer = SmtpMailer(host="mailpit", port=1025, sender="RecliniQ <no-reply@recliniq.local>")

    with caplog.at_level(logging.INFO, logger="app.mail"):
        await mailer.send(MESSAGE)

    assert sent["hostname"] == "mailpit"
    assert sent["port"] == 1025
    mime = sent["message"]
    assert mime["To"] == "juan@example.com"
    assert mime["From"] == "RecliniQ <no-reply@recliniq.local>"
    assert mime.is_multipart()
    (event,) = mail_events(caplog)
    assert event["event"] == "email_sent"
    assert event["to"] == "j***@example.com"


async def test_smtp_failure_is_logged_not_raised(caplog: pytest.LogCaptureFixture) -> None:
    mailer = SmtpMailer(host="127.0.0.1", port=1, sender="x@recliniq.local", timeout_seconds=2)

    with caplog.at_level(logging.INFO, logger="app.mail"):
        await mailer.send(MESSAGE)  # nothing listens on port 1: must not raise

    (failure,) = mail_events(caplog)
    assert failure["event"] == "email_send_failed"
    assert failure["to"] == "j***@example.com"
    assert "secret-token-123" not in caplog.text
    assert "juan@example.com" not in caplog.text


# --- US-01.3: JWT, rehash, reset email --------------------------------------------------

SECRET = "s" * 48


class _Clock:
    def __init__(self, now: datetime) -> None:
        self.current = now

    def now(self) -> datetime:
        return self.current


def _user() -> User:
    return User(
        email="juan@example.com",
        mobile="+639171234567",
        password_hash="x",
        first_name="Juan",
        last_name="Dela Cruz",
        role=Role.DOCTOR,
        privacy_consent_at=datetime.now(UTC),
        privacy_notice_version="v1",
    )


def test_access_token_round_trip_without_personal_data() -> None:
    issuer = JwtTokenIssuer(secret=SECRET, ttl_minutes=15, clock=_Clock(datetime.now(UTC)))
    user = _user()

    issued = issuer.issue_access(user)
    claims = issuer.decode_access(issued.token)

    assert issued.expires_in == 900
    assert claims.user_id == user.id
    assert claims.role is Role.DOCTOR
    raw = pyjwt.decode(issued.token, options={"verify_signature": False})
    assert "juan" not in str(raw).lower()
    assert set(raw) == {"sub", "role", "iss", "aud", "iat", "exp", "jti"}


def test_expired_token_rejected() -> None:
    clock = _Clock(datetime.now(UTC) - timedelta(minutes=16))
    token = JwtTokenIssuer(secret=SECRET, ttl_minutes=15, clock=clock).issue_access(_user()).token
    with pytest.raises(NotAuthenticatedError):
        JwtTokenIssuer(
            secret=SECRET, ttl_minutes=15, clock=_Clock(datetime.now(UTC))
        ).decode_access(token)


def test_tampered_wrong_secret_and_wrong_audience_rejected() -> None:
    now = datetime.now(UTC)
    issuer = JwtTokenIssuer(secret=SECRET, ttl_minutes=15, clock=_Clock(now))
    token = issuer.issue_access(_user()).token
    header, payload, signature = token.split(".")
    tampered = f"{header}.{payload}.{signature[:-2]}AA"
    other_secret = JwtTokenIssuer(secret="o" * 48, ttl_minutes=15, clock=_Clock(now))
    wrong_aud = pyjwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "role": "doctor",
            "iss": "recliniq",
            "aud": "other",
            "iat": now,
            "exp": now + timedelta(minutes=5),
        },
        SECRET,
        algorithm="HS256",
    )
    none_alg = pyjwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "role": "admin",
            "iss": "recliniq",
            "aud": "recliniq-api",
            "iat": now,
            "exp": now + timedelta(minutes=5),
        },
        None,
        algorithm="none",
    )

    for bad in (tampered, wrong_aud, none_alg, "not-a-jwt", ""):
        with pytest.raises(NotAuthenticatedError):
            issuer.decode_access(bad)
    with pytest.raises(NotAuthenticatedError):
        other_secret.decode_access(token)


async def test_needs_rehash_for_weaker_parameters() -> None:
    weak = Argon2(time_cost=1, memory_cost=8 * 1024, parallelism=1)
    hasher = Argon2PasswordHasher()

    weak_hash = weak.hash(PASSWORD)
    assert hasher.needs_rehash(weak_hash)
    assert await hasher.verify(weak_hash, PASSWORD)  # still verifies before the upgrade
    assert not hasher.needs_rehash(await hasher.hash(PASSWORD))


def test_password_reset_email() -> None:
    link = password_reset_link("http://localhost:5173/", "t0k-_")
    assert link == "http://localhost:5173/reset-password?token=t0k-_"
    message = password_reset_email(
        to="juan@example.com", first_name="<Juan>", link=link, ttl_minutes=60, app_name="RecliniQ"
    )
    assert link in message.text
    assert f'href="{link}"' in message.html
    assert "&lt;Juan&gt;" in message.html
    assert "60 minutes" in message.text
