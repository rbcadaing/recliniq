"""Session use cases: login, refresh (rotation + reuse detection), logout, password reset."""

import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import ClassVar

from app.application.accounts.emails import password_reset_email, password_reset_link
from app.application.accounts.ports import (
    Clock,
    EmailMessage,
    PasswordHasher,
    RateLimiter,
    RefreshTokenRepository,
    TokenIssuer,
    TokenRepository,
    UserRepository,
)
from app.application.accounts.services import enforce_rate_limit, hash_token
from app.domain.accounts.entities import RefreshToken, User, VerificationToken
from app.domain.errors import (
    DomainValidationError,
    EmailNotVerifiedError,
    InvalidCredentialsError,
    InvalidTokenError,
    TokenExpiredError,
)

# A real Argon2 verify runs even when no account matches, so timing doesn't reveal accounts.
_DUMMY_PASSWORD = "dummy-password-for-timing-equalization"  # noqa: S105


@dataclass(frozen=True)
class SessionSettings:
    app_name: str
    frontend_base_url: str
    refresh_token_ttl_days: int
    password_reset_ttl_minutes: int
    login_window_seconds: int
    login_per_ip: int
    login_per_email: int
    forgot_window_seconds: int
    forgot_per_ip: int
    forgot_per_email: int


@dataclass(frozen=True)
class IssuedSession:
    access_token: str
    access_expires_in: int
    refresh_token: str
    refresh_expires_in: int


class _SessionService:
    def __init__(
        self,
        *,
        users: UserRepository,
        refresh_tokens: RefreshTokenRepository,
        issuer: TokenIssuer,
        clock: Clock,
        settings: SessionSettings,
    ) -> None:
        self._users = users
        self._refresh_tokens = refresh_tokens
        self._issuer = issuer
        self._clock = clock
        self._settings = settings

    async def _issue(
        self, user: User, *, family_id: uuid.UUID | None = None, expires_at: datetime | None = None
    ) -> IssuedSession:
        """Access token + a new refresh token, in a new family or continuing one."""
        now = self._clock.now()
        expires_at = expires_at or now + timedelta(days=self._settings.refresh_token_ttl_days)
        refresh = secrets.token_urlsafe(32)
        await self._refresh_tokens.add(
            RefreshToken(
                user_id=user.id,
                family_id=family_id or uuid.uuid4(),
                token_hash=hash_token(refresh),
                expires_at=expires_at,
            )
        )
        access = self._issuer.issue_access(user)
        return IssuedSession(
            access_token=access.token,
            access_expires_in=access.expires_in,
            refresh_token=refresh,
            refresh_expires_in=max(0, int((expires_at - now).total_seconds())),
        )


class Login(_SessionService):
    # One dummy hash per hasher implementation, computed lazily with its own parameters.
    _dummy_hashes: ClassVar[dict[type, str]] = {}

    def __init__(
        self,
        *,
        hasher: PasswordHasher,
        limiter: RateLimiter,
        users: UserRepository,
        refresh_tokens: RefreshTokenRepository,
        issuer: TokenIssuer,
        clock: Clock,
        settings: SessionSettings,
    ) -> None:
        super().__init__(
            users=users,
            refresh_tokens=refresh_tokens,
            issuer=issuer,
            clock=clock,
            settings=settings,
        )
        self._hasher = hasher
        self._limiter = limiter

    async def _dummy(self) -> str:
        kind = type(self._hasher)
        if kind not in Login._dummy_hashes:
            Login._dummy_hashes[kind] = await self._hasher.hash(_DUMMY_PASSWORD)
        return Login._dummy_hashes[kind]

    async def __call__(self, email: str, password: str, *, client_ip: str) -> IssuedSession:
        settings = self._settings
        # Over the limit: stop before any password check.
        await enforce_rate_limit(
            self._limiter,
            "login",
            client_ip=client_ip,
            email=email,
            per_ip=settings.login_per_ip,
            per_email=settings.login_per_email,
            window_seconds=settings.login_window_seconds,
        )
        user = await self._users.find_by_email(email)
        stored_hash = user.password_hash if user else await self._dummy()
        password_ok = await self._hasher.verify(stored_hash, password)
        if user is None or not password_ok:
            raise InvalidCredentialsError
        if not user.is_email_verified:
            raise EmailNotVerifiedError  # only reachable with the correct password
        if self._hasher.needs_rehash(user.password_hash):
            await self._users.update_password(user.id, await self._hasher.hash(password))
        return await self._issue(user)


@dataclass(frozen=True)
class RefreshRejected:
    """Returned (not raised) so revocations made on reuse are committed with the response."""

    reuse_detected: bool = False


class RefreshSession(_SessionService):
    async def __call__(self, refresh_token: str) -> IssuedSession | RefreshRejected:
        now = self._clock.now()
        stored = await self._refresh_tokens.find_by_hash(hash_token(refresh_token))
        if stored is None or stored.revoked_at is not None:
            return RefreshRejected()
        if stored.used_at is not None:
            # A rotated-out token came back: someone else has a copy. Kill the whole session.
            await self._refresh_tokens.revoke_family(stored.family_id, now)
            return RefreshRejected(reuse_detected=True)
        if stored.expires_at <= now:
            return RefreshRejected()
        user = await self._users.find(stored.user_id)
        if user is None or not user.is_email_verified:
            await self._refresh_tokens.revoke_family(stored.family_id, now)
            return RefreshRejected()
        await self._refresh_tokens.mark_used(stored.id, now)
        return await self._issue(user, family_id=stored.family_id, expires_at=stored.expires_at)


class Logout:
    def __init__(self, *, refresh_tokens: RefreshTokenRepository, clock: Clock) -> None:
        self._refresh_tokens = refresh_tokens
        self._clock = clock

    async def __call__(self, refresh_token: str) -> None:
        """Revoke the token's session. Unknown or already-revoked tokens are fine (idempotent)."""
        stored = await self._refresh_tokens.find_by_hash(hash_token(refresh_token))
        if stored is not None:
            await self._refresh_tokens.revoke_family(stored.family_id, self._clock.now())


class RequestPasswordReset:
    def __init__(
        self,
        *,
        users: UserRepository,
        reset_tokens: TokenRepository,
        limiter: RateLimiter,
        clock: Clock,
        settings: SessionSettings,
    ) -> None:
        self._users = users
        self._reset_tokens = reset_tokens
        self._limiter = limiter
        self._clock = clock
        self._settings = settings

    async def __call__(self, email: str, *, client_ip: str) -> list[EmailMessage]:
        settings = self._settings
        await enforce_rate_limit(
            self._limiter,
            "forgot",
            client_ip=client_ip,
            email=email,
            per_ip=settings.forgot_per_ip,
            per_email=settings.forgot_per_email,
            window_seconds=settings.forgot_window_seconds,
        )
        user = await self._users.find_by_email(email)
        if user is None:
            return []
        await self._reset_tokens.invalidate_unused(user.id)  # newest link wins
        token = secrets.token_urlsafe(32)
        await self._reset_tokens.add(
            VerificationToken(
                user_id=user.id,
                token_hash=hash_token(token),
                expires_at=self._clock.now()
                + timedelta(minutes=settings.password_reset_ttl_minutes),
            )
        )
        return [
            password_reset_email(
                to=user.email,
                first_name=user.first_name,
                link=password_reset_link(settings.frontend_base_url, token),
                ttl_minutes=settings.password_reset_ttl_minutes,
                app_name=settings.app_name,
            )
        ]


class ResetPassword:
    def __init__(
        self,
        *,
        users: UserRepository,
        reset_tokens: TokenRepository,
        refresh_tokens: RefreshTokenRepository,
        hasher: PasswordHasher,
        clock: Clock,
    ) -> None:
        self._users = users
        self._reset_tokens = reset_tokens
        self._refresh_tokens = refresh_tokens
        self._hasher = hasher
        self._clock = clock

    async def __call__(self, token: str, new_password: str) -> None:
        """The request schema already enforced the password policy (length, common list)."""
        stored = await self._reset_tokens.find_by_hash(hash_token(token))
        if stored is None or stored.used_at is not None:
            raise InvalidTokenError
        now = self._clock.now()
        if stored.expires_at <= now:
            raise TokenExpiredError
        user = await self._users.find(stored.user_id)
        if user is None:
            raise InvalidTokenError
        if new_password.strip().lower() == user.email:
            raise DomainValidationError(
                details=[{"field": "new_password", "message": "Must not be your email address."}]
            )

        await self._users.update_password(user.id, await self._hasher.hash(new_password))
        await self._reset_tokens.mark_used(stored.id, now)
        await self._reset_tokens.invalidate_unused(user.id)
        await self._refresh_tokens.revoke_all_for_user(user.id, now)  # sign out everywhere
        if not user.is_email_verified:
            await self._users.mark_email_verified(user.id, now)  # the link proved ownership
