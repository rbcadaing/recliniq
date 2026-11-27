"""Ports the account services depend on. Infrastructure provides the implementations."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.domain.accounts.entities import DoctorProfile, Specialization, User, VerificationToken


class UserRepository(Protocol):
    async def find(self, user_id: uuid.UUID) -> User | None: ...
    async def find_by_email(self, email: str) -> User | None: ...
    async def mobile_exists(self, mobile: str) -> bool: ...
    async def prc_license_exists(self, prc_license_no: str) -> bool: ...

    async def add_doctor(self, user: User, profile: DoctorProfile) -> None:
        """Persist both. Raises ``FieldConflictError`` if a unique value was taken meanwhile."""
        ...

    async def mark_email_verified(self, user_id: uuid.UUID, at: datetime) -> None: ...


class SpecializationRepository(Protocol):
    async def list_all(self) -> list[Specialization]: ...
    async def exists(self, specialization_id: uuid.UUID) -> bool: ...


class TokenRepository(Protocol):
    async def add(self, token: VerificationToken) -> None: ...
    async def find_by_hash(self, token_hash: str) -> VerificationToken | None: ...
    async def mark_used(self, token_id: uuid.UUID, at: datetime) -> None: ...

    async def invalidate_unused(self, user_id: uuid.UUID) -> None:
        """Make every unused token of the user unusable."""
        ...


class PasswordHasher(Protocol):
    async def hash(self, password: str) -> str: ...
    async def verify(self, password_hash: str, password: str) -> bool: ...


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
