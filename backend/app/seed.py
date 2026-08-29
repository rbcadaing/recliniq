from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Practitioner, Tenant, User, UserRole
from app.security import hash_password


def seed_demo(db: Session) -> None:
    tenant = db.scalars(select(Tenant).where(Tenant.name == settings.seed_tenant_name)).first()
    if tenant is None:
        tenant = Tenant(name=settings.seed_tenant_name, timezone=settings.seed_tenant_tz)
        db.add(tenant)
        db.flush()

    doctor = db.scalars(
        select(User).where(User.tenant_id == tenant.id, User.email == settings.seed_doctor_email)
    ).first()
    if doctor is None:
        doctor = User(
            tenant_id=tenant.id,
            email=settings.seed_doctor_email,
            password_hash=hash_password(settings.seed_doctor_password),
            role=UserRole.doctor.value,
            display_name="Dr. Demo",
        )
        db.add(doctor)
        db.flush()
    if doctor.practitioner is None and db.scalars(
        select(Practitioner).where(Practitioner.user_id == doctor.id)
    ).first() is None:
        db.add(
            Practitioner(
                tenant_id=tenant.id,
                user_id=doctor.id,
                display_name="Dr. Demo",
            )
        )

    assistant = db.scalars(
        select(User).where(User.tenant_id == tenant.id, User.email == settings.seed_assistant_email)
    ).first()
    if assistant is None:
        db.add(
            User(
                tenant_id=tenant.id,
                email=settings.seed_assistant_email,
                password_hash=hash_password(settings.seed_assistant_password),
                role=UserRole.assistant.value,
                display_name="Clinic Assistant",
            )
        )
    db.commit()


if __name__ == "__main__":
    from app.db import SessionLocal

    session = SessionLocal()
    try:
        seed_demo(session)
        print("seed ok")
    finally:
        session.close()
