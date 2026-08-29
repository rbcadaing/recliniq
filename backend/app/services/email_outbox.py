import logging
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import EmailOutbox

log = logging.getLogger("recliniq.email")


def process_outbox(db: Session, limit: int = 20) -> int:
    rows = db.scalars(
        select(EmailOutbox).where(EmailOutbox.sent_at.is_(None)).limit(limit)
    ).all()
    sent = 0
    for row in rows:
        try:
            if settings.smtp_host:
                msg = EmailMessage()
                msg["From"] = settings.smtp_from
                msg["To"] = row.to_email
                msg["Subject"] = row.subject
                msg.set_content(row.body)
                with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
                    smtp.starttls()
                    if settings.smtp_user:
                        smtp.login(settings.smtp_user, settings.smtp_password)
                    smtp.send_message(msg)
            else:
                log.info("email outbox %s -> %s: %s", row.id, row.to_email, row.subject)
            row.sent_at = datetime.now(timezone.utc)
            row.last_error = None
            sent += 1
        except Exception as exc:  # noqa: BLE001
            row.last_error = str(exc)
    db.commit()
    return sent
