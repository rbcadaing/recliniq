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


@dataclass(frozen=True)
class AccessClaims:
    user_id: uuid.UUID
    role: Role


@dataclass(frozen=True)
class IssuedAccessToken:
    token: str
    expires_in: int  # seconds


@dataclass
class RefreshToken:
    """One link in a session's rotation chain (``family_id``). Only the hash is stored."""

    user_id: uuid.UUID
    family_id: uuid.UUID
    token_hash: str
    expires_at: datetime
    used_at: datetime | None = None
    revoked_at: datetime | None = None
    id: uuid.UUID = field(default_factory=uuid.uuid4)


@dataclass(frozen=True)
class DoctorSummary:
    specialization: Specialization
    license_status: LicenseStatus


@dataclass(frozen=True)
class AccountProfile:
    id: uuid.UUID
    first_name: str
    middle_name: str | None
    last_name: str
    email: str
    role: Role
    email_verified: bool
    doctor: DoctorSummary | None = None
