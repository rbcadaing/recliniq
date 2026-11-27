"""Mailer adapters. Failures are logged (address masked, no message body) instead of raised."""

from email.message import EmailMessage as MimeMessage

import aiosmtplib
import structlog

from app.application.accounts.ports import EmailMessage

logger = structlog.get_logger("app.mail")


def mask_email(address: str) -> str:
    """``juan@example.com`` -> ``j***@example.com``."""
    local, _, domain = address.partition("@")
    return f"{local[:1]}***@{domain}" if domain else "***"


class SmtpMailer:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        sender: str,
        username: str | None = None,
        password: str | None = None,
        start_tls: bool = False,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._host = host
        self._port = port
        self._sender = sender
        self._username = username
        self._password = password
        self._start_tls = start_tls
        self._timeout = timeout_seconds

    async def send(self, message: EmailMessage) -> None:
        mime = MimeMessage()
        mime["From"] = self._sender
        mime["To"] = message.to
        mime["Subject"] = message.subject
        mime.set_content(message.text)
        mime.add_alternative(message.html, subtype="html")
        try:
            await aiosmtplib.send(
                mime,
                hostname=self._host,
                port=self._port,
                username=self._username,
                password=self._password,
                start_tls=self._start_tls,
                timeout=self._timeout,
            )
        except (aiosmtplib.SMTPException, OSError) as exc:
            logger.warning(
                "email_send_failed",
                to=mask_email(message.to),
                subject=message.subject,
                error=type(exc).__name__,
            )
            return
        logger.info("email_sent", to=mask_email(message.to), subject=message.subject)


class InMemoryMailer:
    """Test double: keeps sent messages in ``outbox``."""

    def __init__(self) -> None:
        self.outbox: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> None:
        self.outbox.append(message)
