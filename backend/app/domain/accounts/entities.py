"""Account entities. Plain dataclasses: repositories map them to and from ORM models."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from app.domain.accounts.values import LicenseStatus, Role


@dataclass(frozen=True)
class Specialization:
    id: uuid.UUID
    code: str
    name: str


@dataclass
class User:
    email: str
    mobile: str
    password_hash: str
    first_name: str
    last_name: str
    role: Role
    privacy_consent_at: datetime
    privacy_notice_version: str
    middle_name: str | None = None
    email_verified_at: datetime | None = None
    id: uuid.UUID = field(default_factory=uuid.uuid4)

    @property
    def is_email_verified(self) -> bool:
        return self.email_verified_at is not None


@dataclass
class DoctorProfile:
    user_id: uuid.UUID
    specialization_id: uuid.UUID
    prc_license_no: str
    license_status: LicenseStatus = LicenseStatus.PENDING


@dataclass
class VerificationToken:
    user_id: uuid.UUID
    token_hash: str
    expires_at: datetime
    used_at: datetime | None = None
    id: uuid.UUID = field(default_factory=uuid.uuid4)
