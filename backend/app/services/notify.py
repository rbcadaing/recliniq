from sqlalchemy.orm import Session

from app.models import EmailOutbox, InAppAlert, Practitioner, User


def emit_event(
    db: Session,
    *,
    tenant_id: int,
    patient: User,
    practitioner: Practitioner,
    event_type: str,
    body: str,
) -> None:
    practitioner_user = db.get(User, practitioner.user_id)
    recipients: list[User] = [patient]
    if practitioner_user and practitioner_user.id != patient.id:
        recipients.append(practitioner_user)
    seen: set[int] = set()
    for user in recipients:
        if user.id in seen:
            continue
        seen.add(user.id)
        db.add(
            InAppAlert(
                tenant_id=tenant_id,
                user_id=user.id,
                event_type=event_type,
                body=body,
            )
        )
        db.add(
            EmailOutbox(
                tenant_id=tenant_id,
                to_email=user.email,
                subject=f"RecLinq: {event_type}",
                body=body,
            )
        )
