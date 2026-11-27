"""Account services with in-memory fakes for every port."""

import re
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.application.accounts.ports import RateLimitDecision
from app.application.accounts.services import (
    AccountSettings,
    ConfirmEmail,
    DoctorSignUp,
    ResendVerification,
    SignUpDoctor,
    hash_token,
)
from app.domain.accounts.entities import DoctorProfile, Specialization, User, VerificationToken
from app.domain.accounts.values import LicenseStatus, Role
from app.domain.errors import (
    DomainValidationError,
    FieldConflictError,
    InvalidTokenError,
    RateLimitedError,
    TokenExpiredError,
)

NOW = datetime(2026, 11, 27, 10, 0, tzinfo=UTC)
SPECIALIZATION = Specialization(id=uuid.uuid4(), code="pediatrics", name="Pediatrics")
SETTINGS = AccountSettings(
    app_name="RecliniQ",
    frontend_base_url="http://localhost:5173",
    verification_ttl_hours=24,
    privacy_notice_version="v1",
    rate_limit_window_seconds=3600,
    signup_per_ip=5,
    signup_per_email=3,
    resend_per_ip=10,
    resend_per_email=3,
)
TOKEN_IN_LINK = re.compile(r"verify-email\?token=([\w-]+)")


class FakeUsers:
    def __init__(self) -> None:
        self.users: dict[uuid.UUID, User] = {}
        self.profiles: dict[uuid.UUID, DoctorProfile] = {}

    async def find(self, user_id: uuid.UUID) -> User | None:
        return self.users.get(user_id)

    async def find_by_email(self, email: str) -> User | None:
        return next((u for u in self.users.values() if u.email == email), None)

    async def mobile_exists(self, mobile: str) -> bool:
        return any(u.mobile == mobile for u in self.users.values())

    async def prc_license_exists(self, prc_license_no: str) -> bool:
        return any(p.prc_license_no == prc_license_no for p in self.profiles.values())

    async def add_doctor(self, user: User, profile: DoctorProfile) -> None:
        self.users[user.id] = user
        self.profiles[user.id] = profile

    async def mark_email_verified(self, user_id: uuid.UUID, at: datetime) -> None:
        self.users[user_id].email_verified_at = at


class FakeSpecializations:
    async def list_all(self) -> list[Specialization]:
        return [SPECIALIZATION]

    async def exists(self, specialization_id: uuid.UUID) -> bool:
        return specialization_id == SPECIALIZATION.id


class FakeTokens:
    def __init__(self) -> None:
        self.tokens: list[VerificationToken] = []
        self.invalidated: set[uuid.UUID] = set()

    async def add(self, token: VerificationToken) -> None:
        self.tokens.append(token)

    async def find_by_hash(self, token_hash: str) -> VerificationToken | None:
        return next(
            (t for t in self.tokens if t.token_hash == token_hash and t.id not in self.invalidated),
            None,
        )

    async def mark_used(self, token_id: uuid.UUID, at: datetime) -> None:
        next(t for t in self.tokens if t.id == token_id).used_at = at

    async def invalidate_unused(self, user_id: uuid.UUID) -> None:
        self.invalidated |= {t.id for t in self.tokens if t.user_id == user_id and not t.used_at}


class FakeHasher:
    def __init__(self) -> None:
        self.calls = 0

    async def hash(self, password: str) -> str:
        self.calls += 1
        return f"hashed({len(password)})"

    async def verify(self, password_hash: str, password: str) -> bool:
        return password_hash == f"hashed({len(password)})"


class FakeLimiter:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    async def hit(self, bucket: str, *, limit: int, window_seconds: int) -> RateLimitDecision:
        self.counts[bucket] = self.counts.get(bucket, 0) + 1
        if self.counts[bucket] > limit:
            return RateLimitDecision(allowed=False, retry_after_seconds=42)
        return RateLimitDecision(allowed=True)


class FakeClock:
    def __init__(self) -> None:
        self.current = NOW

    def now(self) -> datetime:
        return self.current


class World:
    def __init__(self) -> None:
        self.users = FakeUsers()
        self.tokens = FakeTokens()
        self.hasher = FakeHasher()
        self.limiter = FakeLimiter()
        self.clock = FakeClock()
        common = {
            "users": self.users,
            "tokens": self.tokens,
            "limiter": self.limiter,
            "clock": self.clock,
            "settings": SETTINGS,
        }
        self.sign_up = SignUpDoctor(
            specializations=FakeSpecializations(), hasher=self.hasher, **common
        )
        self.confirm = ConfirmEmail(**common)
        self.resend = ResendVerification(**common)


@pytest.fixture
def world() -> World:
    return World()


def command(**overrides: object) -> DoctorSignUp:
    values: dict[str, object] = {
        "first_name": "Juan",
        "middle_name": None,
        "last_name": "Dela Cruz",
        "email": "doc@example.com",
        "mobile": "+639171234567",
        "password": "correct horse battery staple",
        "specialization_id": SPECIALIZATION.id,
        "prc_license_no": "0012345",
    }
    values.update(overrides)
    return DoctorSignUp(**values)  # type: ignore[arg-type]


def token_from(text: str) -> str:
    match = TOKEN_IN_LINK.search(text)
    assert match is not None
    return match.group(1)


# --- Sign-up ----------------------------------------------------------------------------


async def test_sign_up_creates_pending_unverified_doctor(world: World) -> None:
    emails = await world.sign_up(command(), client_ip="203.0.113.7")

    (user,) = world.users.users.values()
    assert user.role is Role.DOCTOR
    assert user.email_verified_at is None
    assert user.password_hash == "hashed(28)"
    assert user.privacy_consent_at == NOW
    assert user.privacy_notice_version == "v1"
    assert world.users.profiles[user.id].license_status is LicenseStatus.PENDING

    (email,) = emails
    assert email.to == "doc@example.com"
    token = token_from(email.text)
    (stored,) = world.tokens.tokens
    assert stored.token_hash == hash_token(token) != token
    assert stored.expires_at == NOW + timedelta(hours=24)


async def test_registered_verified_email_gets_notice_not_account(world: World) -> None:
    await world.sign_up(command(), client_ip="1.1.1.1")
    (existing,) = world.users.users.values()
    existing.email_verified_at = NOW
    hashes_before = world.hasher.calls

    emails = await world.sign_up(
        command(mobile="+639180000000", prc_license_no="7654321"), client_ip="1.1.1.1"
    )

    assert len(world.users.users) == 1
    assert world.hasher.calls == hashes_before + 1  # hashed anyway, for similar timing
    (email,) = emails
    assert email.to == "doc@example.com"
    assert "already have" in email.subject


async def test_registered_unverified_email_gets_new_link(world: World) -> None:
    first = await world.sign_up(command(), client_ip="1.1.1.1")
    old_token = token_from(first[0].text)

    emails = await world.sign_up(
        command(mobile="+639180000000", prc_license_no="7654321"), client_ip="1.1.1.1"
    )

    assert len(world.users.users) == 1
    new_token = token_from(emails[0].text)
    assert new_token != old_token
    assert await world.tokens.find_by_hash(hash_token(old_token)) is None


async def test_unknown_specialization_rejected_before_email_lookup(world: World) -> None:
    await world.sign_up(command(), client_ip="1.1.1.1")

    with pytest.raises(DomainValidationError) as exc_info:
        # Registered email: still a 422, so the response doesn't depend on the email.
        await world.sign_up(command(specialization_id=uuid.uuid4()), client_ip="1.1.1.1")

    assert exc_info.value.details[0]["field"] == "specialization_id"


@pytest.mark.parametrize(
    ("override", "field"),
    [({"mobile": "+639171234567"}, "mobile"), ({"prc_license_no": "0012345"}, "prc_license_no")],
)
@pytest.mark.parametrize("email", ["doc@example.com", "someone-new@example.com"])
async def test_mobile_and_prc_conflicts_regardless_of_email(
    world: World, override: dict[str, str], field: str, email: str
) -> None:
    await world.sign_up(command(), client_ip="1.1.1.1")
    values = {"email": email, "mobile": "+639180000000", "prc_license_no": "7654321"}
    values.update(override)

    with pytest.raises(FieldConflictError) as exc_info:
        await world.sign_up(command(**values), client_ip="2.2.2.2")

    assert exc_info.value.details == {"field": field}
    assert len(world.users.users) == 1


async def test_sign_up_rate_limited_per_ip(world: World) -> None:
    for i in range(5):
        await world.sign_up(
            command(email=f"d{i}@example.com", mobile=f"+63917000000{i}", prc_license_no=str(i)),
            client_ip="9.9.9.9",
        )

    with pytest.raises(RateLimitedError) as exc_info:
        await world.sign_up(command(email="d9@example.com"), client_ip="9.9.9.9")

    assert exc_info.value.retry_after_seconds == 42
    assert len(world.users.users) == 5


async def test_sign_up_rate_limited_per_email_across_ips(world: World) -> None:
    for i in range(3):
        await world.sign_up(
            command(mobile=f"+63917000000{i}", prc_license_no=str(i)), client_ip=f"10.0.0.{i}"
        )

    with pytest.raises(RateLimitedError):
        await world.sign_up(
            command(mobile="+639179999999", prc_license_no="99"), client_ip="10.0.0.99"
        )


# --- Confirm ----------------------------------------------------------------------------


async def test_confirm_valid_token_verifies_once(world: World) -> None:
    token = token_from((await world.sign_up(command(), client_ip="1.1.1.1"))[0].text)
    world.clock.current = NOW + timedelta(hours=1)

    await world.confirm(token)

    (user,) = world.users.users.values()
    assert user.email_verified_at == NOW + timedelta(hours=1)
    with pytest.raises(InvalidTokenError):
        await world.confirm(token)


async def test_confirm_expired_token(world: World) -> None:
    token = token_from((await world.sign_up(command(), client_ip="1.1.1.1"))[0].text)
    world.clock.current = NOW + timedelta(hours=24)

    with pytest.raises(TokenExpiredError):
        await world.confirm(token)

    (user,) = world.users.users.values()
    assert user.email_verified_at is None


async def test_confirm_unknown_token(world: World) -> None:
    with pytest.raises(InvalidTokenError):
        await world.confirm("never-issued")


# --- Resend -----------------------------------------------------------------------------


async def test_resend_issues_new_link_and_invalidates_old(world: World) -> None:
    old = token_from((await world.sign_up(command(), client_ip="1.1.1.1"))[0].text)

    (email,) = await world.resend("doc@example.com", client_ip="1.1.1.1")

    new = token_from(email.text)
    with pytest.raises(InvalidTokenError):
        await world.confirm(old)
    await world.confirm(new)


async def test_resend_for_unknown_or_verified_sends_nothing(world: World) -> None:
    assert await world.resend("nobody@example.com", client_ip="1.1.1.1") == []

    token = token_from((await world.sign_up(command(), client_ip="1.1.1.1"))[0].text)
    await world.confirm(token)
    assert await world.resend("doc@example.com", client_ip="1.1.1.1") == []


async def test_resend_rate_limited_per_email(world: World) -> None:
    for _ in range(3):
        await world.resend("doc@example.com", client_ip="1.1.1.1")

    with pytest.raises(RateLimitedError):
        await world.resend("doc@example.com", client_ip="5.5.5.5")
