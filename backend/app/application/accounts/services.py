"""Account use cases: doctor sign-up, email confirmation, and resending verification.

Services return the emails to send instead of sending them. The caller delivers them after the
response is sent, so delivery can't fail the request and both duplicate-email paths look the
same from outside.
"""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import timedelta

from app.application.accounts.emails import (
    account_exists_email,
    verification_email,
    verification_link,
)
from app.application.accounts.ports import (
    Clock,
    EmailMessage,
    PasswordHasher,
    RateLimiter,
    SpecializationRepository,
    TokenRepository,
    UserRepository,
)
from app.domain.accounts.entities import DoctorProfile, User, VerificationToken
from app.domain.accounts.values import Role
from app.domain.errors import (
    DomainValidationError,
    FieldConflictError,
    InvalidTokenError,
    RateLimitedError,
    TokenExpiredError,
)


@dataclass(frozen=True)
class AccountSettings:
    app_name: str
    frontend_base_url: str
    verification_ttl_hours: int
    privacy_notice_version: str
    rate_limit_window_seconds: int
    signup_per_ip: int
    signup_per_email: int
    resend_per_ip: int
    resend_per_email: int


@dataclass(frozen=True)
class DoctorSignUp:
    """Already parsed and normalized by the request schema (see app.domain.accounts.values)."""

    first_name: str
    middle_name: str | None
    last_name: str
    email: str
    mobile: str
    password: str
    specialization_id: uuid.UUID
    prc_license_no: str


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def rate_limit_bucket(action: str, kind: str, value: str) -> str:
    """``action:kind:<sha256>``. Raw IPs and emails are never stored."""
    digest = hashlib.sha256(value.strip().lower().encode()).hexdigest()
    return f"{action}:{kind}:{digest}"


async def enforce_rate_limit(
    limiter: RateLimiter,
    action: str,
    *,
    client_ip: str,
    email: str,
    per_ip: int,
    per_email: int,
    window_seconds: int,
) -> None:
    """Count one attempt per IP and per email; raise ``RateLimitedError`` if either is over."""
    decisions = [
        await limiter.hit(
            rate_limit_bucket(action, "ip", client_ip), limit=per_ip, window_seconds=window_seconds
        ),
        await limiter.hit(
            rate_limit_bucket(action, "email", email),
            limit=per_email,
            window_seconds=window_seconds,
        ),
    ]
    denied = [d for d in decisions if not d.allowed]
    if denied:
        raise RateLimitedError(max(d.retry_after_seconds for d in denied))


class _AccountService:
    def __init__(
        self,
        *,
        users: UserRepository,
        tokens: TokenRepository,
        limiter: RateLimiter,
        clock: Clock,
        settings: AccountSettings,
    ) -> None:
        self._users = users
        self._tokens = tokens
        self._limiter = limiter
        self._clock = clock
        self._settings = settings

    async def _enforce_rate_limit(
        self, action: str, *, client_ip: str, email: str, per_ip: int, per_email: int
    ) -> None:
        await enforce_rate_limit(
            self._limiter,
            action,
            client_ip=client_ip,
            email=email,
            per_ip=per_ip,
            per_email=per_email,
            window_seconds=self._settings.rate_limit_window_seconds,
        )

    async def _issue_verification(self, user: User) -> EmailMessage:
        """Invalidate earlier unused links and return a verification email with a new one."""
        await self._tokens.invalidate_unused(user.id)
        token = secrets.token_urlsafe(32)
        expires_at = self._clock.now() + timedelta(hours=self._settings.verification_ttl_hours)
        await self._tokens.add(
            VerificationToken(user_id=user.id, token_hash=hash_token(token), expires_at=expires_at)
        )
        return verification_email(
            to=user.email,
            first_name=user.first_name,
            link=verification_link(self._settings.frontend_base_url, token),
            ttl_hours=self._settings.verification_ttl_hours,
            app_name=self._settings.app_name,
        )


class SignUpDoctor(_AccountService):
    def __init__(
        self,
        *,
        specializations: SpecializationRepository,
        hasher: PasswordHasher,
        users: UserRepository,
        tokens: TokenRepository,
        limiter: RateLimiter,
        clock: Clock,
        settings: AccountSettings,
    ) -> None:
        super().__init__(
            users=users, tokens=tokens, limiter=limiter, clock=clock, settings=settings
        )
        self._specializations = specializations
        self._hasher = hasher

    async def __call__(self, command: DoctorSignUp, *, client_ip: str) -> list[EmailMessage]:
        settings = self._settings
        await self._enforce_rate_limit(
            "signup",
            client_ip=client_ip,
            email=command.email,
            per_ip=settings.signup_per_ip,
            per_email=settings.signup_per_email,
        )
        # Every outcome that isn't 202 is decided before looking at the email, so the response
        # never depends on whether the email is registered.
        if not await self._specializations.exists(command.specialization_id):
            raise DomainValidationError(
                details=[{"field": "specialization_id", "message": "Unknown specialization."}]
            )
        if await self._users.mobile_exists(command.mobile):
            raise FieldConflictError("mobile")
        if await self._users.prc_license_exists(command.prc_license_no):
            raise FieldConflictError(
                "prc_license_no", "This PRC license number is already registered."
            )

        # Hash on every path so registered and new emails take similar time.
        password_hash = await self._hasher.hash(command.password)

        existing = await self._users.find_by_email(command.email)
        if existing is not None:
            if existing.is_email_verified:
                return [
                    account_exists_email(
                        to=existing.email,
                        first_name=existing.first_name,
                        app_name=settings.app_name,
                    )
                ]
            return [await self._issue_verification(existing)]

        user = User(
            email=command.email,
            mobile=command.mobile,
            password_hash=password_hash,
            first_name=command.first_name,
            middle_name=command.middle_name,
            last_name=command.last_name,
            role=Role.DOCTOR,
            privacy_consent_at=self._clock.now(),
            privacy_notice_version=settings.privacy_notice_version,
        )
        profile = DoctorProfile(
            user_id=user.id,
            specialization_id=command.specialization_id,
            prc_license_no=command.prc_license_no,
        )
        await self._users.add_doctor(user, profile)
        return [await self._issue_verification(user)]


class ConfirmEmail(_AccountService):
    async def __call__(self, token: str) -> None:
        stored = await self._tokens.find_by_hash(hash_token(token))
        if stored is None or stored.used_at is not None:
            raise InvalidTokenError
        now = self._clock.now()
        if stored.expires_at <= now:
            raise TokenExpiredError
        user = await self._users.find(stored.user_id)
        if user is None:
            raise InvalidTokenError
        await self._tokens.mark_used(stored.id, now)
        if not user.is_email_verified:
            await self._users.mark_email_verified(user.id, now)


class ResendVerification(_AccountService):
    async def __call__(self, email: str, *, client_ip: str) -> list[EmailMessage]:
        await self._enforce_rate_limit(
            "resend",
            client_ip=client_ip,
            email=email,
            per_ip=self._settings.resend_per_ip,
            per_email=self._settings.resend_per_email,
        )
        user = await self._users.find_by_email(email)
        if user is None or user.is_email_verified:
            return []
        return [await self._issue_verification(user)]
