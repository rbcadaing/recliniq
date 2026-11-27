"""Login, refresh, logout, and password reset services with in-memory fakes."""

import contextlib
import re
import uuid
from datetime import datetime, timedelta

import pytest

from app.application.accounts.ports import EmailMessage
from app.application.accounts.services import hash_token
from app.application.accounts.sessions import (
    IssuedSession,
    Login,
    Logout,
    RefreshRejected,
    RefreshSession,
    RequestPasswordReset,
    ResetPassword,
    SessionSettings,
)
from app.domain.accounts.entities import (
    AccessClaims,
    AccountProfile,
    DoctorProfile,
    IssuedAccessToken,
    RefreshToken,
    User,
)
from app.domain.accounts.values import Role
from app.domain.errors import (
    DomainValidationError,
    EmailNotVerifiedError,
    InvalidCredentialsError,
    InvalidTokenError,
    RateLimitedError,
    TokenExpiredError,
)
from tests.unit.test_account_services import NOW, FakeClock, FakeLimiter, FakeTokens, FakeUsers

PASSWORD = "correct horse battery staple"
SETTINGS = SessionSettings(
    app_name="RecliniQ",
    frontend_base_url="http://localhost:5173",
    refresh_token_ttl_days=30,
    password_reset_ttl_minutes=60,
    login_window_seconds=900,
    login_per_ip=30,
    login_per_email=10,
    forgot_window_seconds=3600,
    forgot_per_ip=10,
    forgot_per_email=3,
)
RESET_LINK = re.compile(r"reset-password\?token=([\w-]+)")


class Users(FakeUsers):
    async def update_password(self, user_id: uuid.UUID, password_hash: str) -> None:
        self.users[user_id].password_hash = password_hash

    async def find_profile(self, user_id: uuid.UUID) -> AccountProfile | None:
        return None


class Hasher:
    """``v1:`` hashes are "outdated"; current hashes are ``v2:``. Counts verify calls."""

    def __init__(self) -> None:
        self.verifies = 0

    async def hash(self, password: str) -> str:
        return f"v2:{password}"

    async def verify(self, password_hash: str, password: str) -> bool:
        self.verifies += 1
        return password_hash.split(":", 1)[1] == password

    def needs_rehash(self, password_hash: str) -> bool:
        return not password_hash.startswith("v2:")


class Issuer:
    def issue_access(self, user: User) -> IssuedAccessToken:
        return IssuedAccessToken(token=f"access-for-{user.id}", expires_in=900)

    def decode_access(self, token: str) -> AccessClaims:
        raise NotImplementedError


class RefreshTokens:
    def __init__(self) -> None:
        self.tokens: list[RefreshToken] = []

    async def add(self, token: RefreshToken) -> None:
        self.tokens.append(token)

    async def find_by_hash(self, token_hash: str) -> RefreshToken | None:
        return next((t for t in self.tokens if t.token_hash == token_hash), None)

    async def mark_used(self, token_id: uuid.UUID, at: datetime) -> None:
        next(t for t in self.tokens if t.id == token_id).used_at = at

    async def revoke_family(self, family_id: uuid.UUID, at: datetime) -> None:
        for t in self.tokens:
            if t.family_id == family_id and t.revoked_at is None:
                t.revoked_at = at

    async def revoke_all_for_user(self, user_id: uuid.UUID, at: datetime) -> None:
        for t in self.tokens:
            if t.user_id == user_id and t.revoked_at is None:
                t.revoked_at = at


class World:
    def __init__(self) -> None:
        self.users = Users()
        self.refresh_tokens = RefreshTokens()
        self.reset_tokens = FakeTokens()
        self.hasher = Hasher()
        self.limiter = FakeLimiter()
        self.clock = FakeClock()
        session = {
            "users": self.users,
            "refresh_tokens": self.refresh_tokens,
            "issuer": Issuer(),
            "clock": self.clock,
            "settings": SETTINGS,
        }
        self.login = Login(hasher=self.hasher, limiter=self.limiter, **session)  # type: ignore[arg-type]
        self.refresh = RefreshSession(**session)  # type: ignore[arg-type]
        self.logout = Logout(refresh_tokens=self.refresh_tokens, clock=self.clock)
        self.forgot = RequestPasswordReset(
            users=self.users,
            reset_tokens=self.reset_tokens,
            limiter=self.limiter,
            clock=self.clock,
            settings=SETTINGS,
        )
        self.reset = ResetPassword(
            users=self.users,
            reset_tokens=self.reset_tokens,
            refresh_tokens=self.refresh_tokens,
            hasher=self.hasher,
            clock=self.clock,
        )

    def add_user(
        self, *, email: str = "doc@example.com", verified: bool = True, hash_prefix: str = "v2"
    ) -> User:
        user = User(
            email=email,
            mobile="+639171234567",
            password_hash=f"{hash_prefix}:{PASSWORD}",
            first_name="Juan",
            last_name="Dela Cruz",
            role=Role.DOCTOR,
            privacy_consent_at=NOW,
            privacy_notice_version="v1",
            email_verified_at=NOW if verified else None,
        )
        self.users.users[user.id] = user
        self.users.profiles[user.id] = DoctorProfile(user.id, uuid.uuid4(), "0012345")
        return user


@pytest.fixture
def world() -> World:
    return World()


def reset_token(emails: list[EmailMessage]) -> str:
    match = RESET_LINK.search(emails[0].text)
    assert match is not None
    return match.group(1)


# --- Login ------------------------------------------------------------------------------


async def test_login_issues_session(world: World) -> None:
    user = world.add_user()

    session = await world.login("doc@example.com", PASSWORD, client_ip="1.1.1.1")

    assert session.access_token == f"access-for-{user.id}"
    assert session.access_expires_in == 900
    assert session.refresh_expires_in == 30 * 24 * 3600
    (stored,) = world.refresh_tokens.tokens
    assert stored.token_hash == hash_token(session.refresh_token) != session.refresh_token


async def test_wrong_password_and_unknown_email_look_the_same(world: World) -> None:
    world.add_user()

    for email, password in [("doc@example.com", "wrong"), ("nobody@example.com", PASSWORD)]:
        before = world.hasher.verifies
        with pytest.raises(InvalidCredentialsError):
            await world.login(email, password, client_ip="1.1.1.1")
        assert world.hasher.verifies == before + 1  # one verify on both paths
    assert world.refresh_tokens.tokens == []


async def test_unverified_email_only_revealed_with_correct_password(world: World) -> None:
    world.add_user(verified=False)

    with pytest.raises(InvalidCredentialsError):
        await world.login("doc@example.com", "wrong", client_ip="1.1.1.1")
    with pytest.raises(EmailNotVerifiedError):
        await world.login("doc@example.com", PASSWORD, client_ip="1.1.1.1")
    assert world.refresh_tokens.tokens == []


async def test_pending_doctor_can_log_in(world: World) -> None:
    world.add_user()  # doctor profile defaults to license_status=pending
    assert isinstance(
        await world.login("doc@example.com", PASSWORD, client_ip="1.1.1.1"), IssuedSession
    )


async def test_over_limit_does_not_check_password(world: World) -> None:
    world.add_user()
    for _ in range(10):
        with contextlib.suppress(InvalidCredentialsError):
            await world.login("doc@example.com", "wrong", client_ip="1.1.1.1")
    verifies = world.hasher.verifies

    with pytest.raises(RateLimitedError):
        await world.login("doc@example.com", PASSWORD, client_ip="1.1.1.1")
    assert world.hasher.verifies == verifies


async def test_outdated_hash_is_upgraded_on_login(world: World) -> None:
    user = world.add_user(hash_prefix="v1")

    await world.login("doc@example.com", PASSWORD, client_ip="1.1.1.1")

    assert world.users.users[user.id].password_hash == f"v2:{PASSWORD}"


# --- Refresh and logout -----------------------------------------------------------------


async def test_refresh_rotates_within_family_keeping_expiry(world: World) -> None:
    world.add_user()
    first = await world.login("doc@example.com", PASSWORD, client_ip="1.1.1.1")
    world.clock.current = NOW + timedelta(days=1)

    second = await world.refresh(first.refresh_token)

    assert isinstance(second, IssuedSession)
    old, new = world.refresh_tokens.tokens
    assert old.used_at == NOW + timedelta(days=1)
    assert new.family_id == old.family_id
    assert new.expires_at == old.expires_at  # absolute expiry, no sliding
    assert second.refresh_expires_in == 29 * 24 * 3600


async def test_reuse_revokes_whole_family(world: World) -> None:
    world.add_user()
    first = await world.login("doc@example.com", PASSWORD, client_ip="1.1.1.1")
    second = await world.refresh(first.refresh_token)
    assert isinstance(second, IssuedSession)

    replay = await world.refresh(first.refresh_token)

    assert replay == RefreshRejected(reuse_detected=True)
    assert all(t.revoked_at is not None for t in world.refresh_tokens.tokens)
    assert isinstance(await world.refresh(second.refresh_token), RefreshRejected)


async def test_expired_unknown_and_deleted_user_tokens_rejected(world: World) -> None:
    user = world.add_user()
    session = await world.login("doc@example.com", PASSWORD, client_ip="1.1.1.1")

    assert isinstance(await world.refresh("never-issued"), RefreshRejected)
    world.clock.current = NOW + timedelta(days=30)
    assert isinstance(await world.refresh(session.refresh_token), RefreshRejected)

    world.clock.current = NOW
    other = await world.login("doc@example.com", PASSWORD, client_ip="1.1.1.1")
    del world.users.users[user.id]  # account soft-deleted meanwhile
    assert isinstance(await world.refresh(other.refresh_token), RefreshRejected)


async def test_logout_revokes_family_and_is_idempotent(world: World) -> None:
    world.add_user()
    session = await world.login("doc@example.com", PASSWORD, client_ip="1.1.1.1")

    await world.logout(session.refresh_token)
    await world.logout(session.refresh_token)
    await world.logout("never-issued")

    assert isinstance(await world.refresh(session.refresh_token), RefreshRejected)


# --- Password reset ---------------------------------------------------------------------


async def test_forgot_password_same_outcome_shape(world: World) -> None:
    world.add_user()

    assert await world.forgot("nobody@example.com", client_ip="1.1.1.1") == []
    (email,) = await world.forgot("doc@example.com", client_ip="1.1.1.1")

    assert email.to == "doc@example.com"
    assert "reset-password?token=" in email.text


async def test_newer_reset_link_invalidates_older(world: World) -> None:
    world.add_user()
    first = reset_token(await world.forgot("doc@example.com", client_ip="1.1.1.1"))
    second = reset_token(await world.forgot("doc@example.com", client_ip="1.1.1.1"))

    with pytest.raises(InvalidTokenError):
        await world.reset(first, "brand new passphrase here")
    await world.reset(second, "brand new passphrase here")


async def test_forgot_password_rate_limited(world: World) -> None:
    for _ in range(3):
        await world.forgot("doc@example.com", client_ip="1.1.1.1")
    with pytest.raises(RateLimitedError):
        await world.forgot("doc@example.com", client_ip="2.2.2.2")


async def test_reset_changes_password_signs_out_and_verifies(world: World) -> None:
    user = world.add_user(verified=False)
    world.users.users[user.id].email_verified_at = NOW  # verified to log in first...
    session = await world.login("doc@example.com", PASSWORD, client_ip="1.1.1.1")
    world.users.users[user.id].email_verified_at = None  # ...then treat as unverified
    token = reset_token(await world.forgot("doc@example.com", client_ip="1.1.1.1"))

    await world.reset(token, "brand new passphrase here")

    stored = world.users.users[user.id]
    assert stored.password_hash == "v2:brand new passphrase here"
    assert stored.email_verified_at == NOW
    assert isinstance(await world.refresh(session.refresh_token), RefreshRejected)
    with pytest.raises(InvalidTokenError):
        await world.reset(token, "another new passphrase")  # single use


async def test_reset_with_expired_or_unknown_token(world: World) -> None:
    user = world.add_user()
    token = reset_token(await world.forgot("doc@example.com", client_ip="1.1.1.1"))
    world.clock.current = NOW + timedelta(minutes=60)

    with pytest.raises(TokenExpiredError):
        await world.reset(token, "brand new passphrase here")
    with pytest.raises(InvalidTokenError):
        await world.reset("never-issued", "brand new passphrase here")
    assert world.users.users[user.id].password_hash == f"v2:{PASSWORD}"


async def test_reset_rejects_email_as_password_without_using_token(world: World) -> None:
    world.add_user()
    token = reset_token(await world.forgot("doc@example.com", client_ip="1.1.1.1"))

    with pytest.raises(DomainValidationError):
        await world.reset(token, "Doc@Example.com")
    await world.reset(token, "brand new passphrase here")  # token still usable
