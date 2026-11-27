"""ORM models for accounts. Every table is soft-deletable except ``rate_limit_counters``."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.accounts.values import LicenseStatus, Role
from app.infrastructure.db.base import Base, SoftDeleteMixin, TimestampMixin, soft_unique_index


def _in(column: str, values: type[Role] | type[LicenseStatus]) -> str:
    return f"{column} IN ({', '.join(repr(v.value) for v in values)})"


class SpecializationModel(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "specializations"
    __table_args__ = (soft_unique_index("uq_specializations_code_active", "code"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(128))


class UserModel(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        soft_unique_index("uq_users_email_active", "email"),
        soft_unique_index("uq_users_mobile_active", "mobile"),
        CheckConstraint("email = lower(email)", name="email_lowercase"),
        CheckConstraint(_in("role", Role), name="role_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(254))
    mobile: Mapped[str] = mapped_column(String(13))
    password_hash: Mapped[str] = mapped_column(String(255))
    first_name: Mapped[str] = mapped_column(String(100))
    middle_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(16))
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    privacy_consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    privacy_notice_version: Mapped[str] = mapped_column(String(32))


class DoctorProfileModel(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "doctor_profiles"
    __table_args__ = (
        soft_unique_index("uq_doctor_profiles_prc_license_no_active", "prc_license_no"),
        CheckConstraint(_in("license_status", LicenseStatus), name="license_status_valid"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    specialization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("specializations.id"), index=True
    )
    prc_license_no: Mapped[str] = mapped_column(String(7))
    license_status: Mapped[str] = mapped_column(String(16), default=LicenseStatus.PENDING.value)
    license_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    license_reviewed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    license_review_note: Mapped[str | None] = mapped_column(Text)


class EmailVerificationTokenModel(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "email_verification_tokens"
    __table_args__ = (soft_unique_index("uq_email_verification_tokens_hash_active", "token_hash"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RateLimitCounterModel(Base):
    """Fixed-window attempt counters. Exempt from soft delete (see SOFT_DELETE_EXEMPT_TABLES)."""

    __tablename__ = "rate_limit_counters"

    bucket: Mapped[str] = mapped_column(String(200), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    count: Mapped[int] = mapped_column(Integer)
