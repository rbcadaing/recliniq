"""Ports the account services depend on. Infrastructure provides the implementations."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.domain.accounts.entities import (
    AccessClaims,
    AccountProfile,
    DoctorProfile,
    IssuedAccessToken,
    RefreshToken,
    Specialization,
    User,
    VerificationToken,
)


class UserRepository(Protocol):
    async def find(self, user_id: uuid.UUID) -> User | None: ...
    async def find_by_email(self, email: str) -> User | None: ...
    async def mobile_exists(self, mobile: str) -> bool: ...
    async def prc_license_exists(self, prc_license_no: str) -> bool: ...

    async def add_doctor(self, user: User, profile: DoctorProfile) -> None:
        """Persist both. Raises ``FieldConflictError`` if a unique value was taken meanwhile."""
        ...

    async def mark_email_verified(self, user_id: uuid.UUID, at: datetime) -> None: ...
    async def update_password(self, user_id: uuid.UUID, password_hash: str) -> None: ...
    async def find_profile(self, user_id: uuid.UUID) -> AccountProfile | None: ...


class SpecializationRepository(Protocol):
    async def list_all(self) -> list[Specialization]: ...
    async def exists(self, specialization_id: uuid.UUID) -> bool: ...


class TokenRepository(Protocol):
    """Single-use, expiring tokens (email verification, password reset). Hashes only."""

    async def add(self, token: VerificationToken) -> None: ...
    async def find_by_hash(self, token_hash: str) -> VerificationToken | None: ...
    async def mark_used(self, token_id: uuid.UUID, at: datetime) -> None: ...

    async def invalidate_unused(self, user_id: uuid.UUID) -> None:
        """Make every unused token of the user unusable."""
        ...


class PasswordHasher(Protocol):
    async def hash(self, password: str) -> str: ...
    async def verify(self, password_hash: str, password: str) -> bool: ...
    def needs_rehash(self, password_hash: str) -> bool: ...


class RefreshTokenRepository(Protocol):
    async def add(self, token: RefreshToken) -> None: ...
    async def find_by_hash(self, token_hash: str) -> RefreshToken | None: ...
    async def mark_used(self, token_id: uuid.UUID, at: datetime) -> None: ...
    async def revoke_family(self, family_id: uuid.UUID, at: datetime) -> None: ...
    async def revoke_all_for_user(self, user_id: uuid.UUID, at: datetime) -> None: ...


class TokenIssuer(Protocol):
    def issue_access(self, user: User) -> IssuedAccessToken: ...

    def decode_access(self, token: str) -> AccessClaims:
        """Raise ``NotAuthenticatedError`` for any invalid, expired, or tampered token."""
        ...


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    text: str
    html: str


class Mailer(Protocol):
    async def send(self, message: EmailMessage) -> None:
        """Deliver the message. Implementations log failures instead of raising."""
        ...


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: int = 0


class RateLimiter(Protocol):
    async def hit(self, bucket: str, *, limit: int, window_seconds: int) -> RateLimitDecision:
        """Count one attempt in ``bucket``. Counts persist even if the request later fails."""
        ...


class Clock(Protocol):
    def now(self) -> datetime: ...
