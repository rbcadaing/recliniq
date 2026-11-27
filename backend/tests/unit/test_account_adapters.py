import logging
from typing import Any

import pytest

from app.application.accounts.emails import (
    account_exists_email,
    verification_email,
    verification_link,
)
from app.application.accounts.ports import EmailMessage
from app.infrastructure.accounts import mailer as mailer_module
from app.infrastructure.accounts.hasher import Argon2PasswordHasher
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
