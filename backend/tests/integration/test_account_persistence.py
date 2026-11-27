"""Account repositories and the rate limiter against real PostgreSQL."""

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.application.accounts.services import rate_limit_bucket as bucket_key
from app.domain.accounts.entities import DoctorProfile, User, VerificationToken
from app.domain.accounts.values import LicenseStatus, Role
from app.domain.errors import FieldConflictError
from app.infrastructure.accounts.models import DoctorProfileModel, UserModel
from app.infrastructure.accounts.rate_limiter import PostgresRateLimiter
from app.infrastructure.accounts.repositories import (
    SqlSpecializationRepository,
    SqlTokenRepository,
    SqlUserRepository,
)

NOW = datetime(2026, 11, 27, 10, 0, tzinfo=UTC)


async def _specialization_id(session: AsyncSession) -> uuid.UUID:
    return (await SqlSpecializationRepository(session).list_all())[0].id


def _doctor(
    specialization_id: uuid.UUID,
    *,
    email: str = "doc@example.com",
    mobile: str = "+639171234567",
    prc: str = "0012345",
) -> tuple[User, DoctorProfile]:
    user = User(
        email=email,
        mobile=mobile,
        password_hash="argon2-hash",
        first_name="Juan",
        last_name="Dela Cruz",
        role=Role.DOCTOR,
        privacy_consent_at=NOW,
        privacy_notice_version="v1",
    )
    return user, DoctorProfile(
        user_id=user.id, specialization_id=specialization_id, prc_license_no=prc
    )


# --- Specializations --------------------------------------------------------------------


async def test_specializations_are_seeded_and_sorted(db_session: AsyncSession) -> None:
    repo = SqlSpecializationRepository(db_session)
    specializations = await repo.list_all()
    names = [s.name for s in specializations]
    assert len(names) >= 20
    assert names == sorted(names)
    assert "Pediatrics" in names
    assert await repo.exists(specializations[0].id)
    assert not await repo.exists(uuid.uuid4())


# --- Users and doctor profiles ----------------------------------------------------------


async def test_add_doctor_and_lookups(db_session: AsyncSession) -> None:
    repo = SqlUserRepository(db_session)
    user, profile = _doctor(await _specialization_id(db_session))

    await repo.add_doctor(user, profile)

    found = await repo.find_by_email("doc@example.com")
    assert found is not None
    assert found.id == user.id
    assert found.role is Role.DOCTOR
    assert not found.is_email_verified
    assert await repo.mobile_exists("+639171234567")
    assert await repo.prc_license_exists("0012345")
    assert not await repo.mobile_exists("+639990000000")
    stored = await db_session.get(DoctorProfileModel, user.id)
    assert stored is not None
    assert stored.license_status == LicenseStatus.PENDING.value


@pytest.mark.parametrize(
    ("override", "field"),
    [
        ({"email": "doc@example.com"}, "email"),
        ({"mobile": "+639171234567"}, "mobile"),
        ({"prc": "0012345"}, "prc_license_no"),
    ],
)
async def test_unique_value_race_maps_to_field_conflict(
    db_session: AsyncSession, override: dict[str, str], field: str
) -> None:
    repo = SqlUserRepository(db_session)
    specialization_id = await _specialization_id(db_session)
    await repo.add_doctor(*_doctor(specialization_id))
    second = {"email": "other@example.com", "mobile": "+639180000000", "prc": "7654321"}
    second.update(override)

    with pytest.raises(FieldConflictError) as exc_info:
        await repo.add_doctor(*_doctor(specialization_id, **second))

    assert exc_info.value.details == {"field": field}
    # The savepoint kept the session usable.
    assert await repo.find_by_email("doc@example.com") is not None


async def test_values_can_be_reused_after_account_is_soft_deleted(
    db_session: AsyncSession,
) -> None:
    repo = SqlUserRepository(db_session)
    specialization_id = await _specialization_id(db_session)
    user, profile = _doctor(specialization_id)
    await repo.add_doctor(user, profile)

    user_row = await db_session.get(UserModel, user.id)
    profile_row = await db_session.get(DoctorProfileModel, user.id)
    assert user_row is not None
    assert profile_row is not None
    await repo.soft_delete(user_row, actor_id=None)
    profile_row.deleted_at = NOW
    await db_session.flush()

    assert await repo.find_by_email("doc@example.com") is None
    await repo.add_doctor(*_doctor(specialization_id))  # same email, mobile, PRC: accepted
    assert await repo.find_by_email("doc@example.com") is not None


async def test_mark_email_verified(db_session: AsyncSession) -> None:
    repo = SqlUserRepository(db_session)
    user, profile = _doctor(await _specialization_id(db_session))
    await repo.add_doctor(user, profile)

    await repo.mark_email_verified(user.id, NOW)

    found = await repo.find(user.id)
    assert found is not None
    assert found.email_verified_at == NOW


# --- Verification tokens ----------------------------------------------------------------


async def test_token_lifecycle(db_session: AsyncSession) -> None:
    users = SqlUserRepository(db_session)
    tokens = SqlTokenRepository(db_session)
    user, profile = _doctor(await _specialization_id(db_session))
    await users.add_doctor(user, profile)
    first = VerificationToken(user_id=user.id, token_hash="a" * 64, expires_at=NOW)
    used = VerificationToken(user_id=user.id, token_hash="b" * 64, expires_at=NOW)
    await tokens.add(first)
    await tokens.add(used)
    await tokens.mark_used(used.id, NOW)

    found = await tokens.find_by_hash("a" * 64)
    assert found is not None
    assert found.user_id == user.id

    await tokens.invalidate_unused(user.id)

    assert await tokens.find_by_hash("a" * 64) is None  # superseded: soft-deleted
    still_used = await tokens.find_by_hash("b" * 64)  # used tokens are left as they are
    assert still_used is not None
    assert still_used.used_at == NOW


# --- Rate limiter -----------------------------------------------------------------------


class FakeClock:
    def __init__(self, now: datetime) -> None:
        self.current = now

    def now(self) -> datetime:
        return self.current


@pytest.fixture
async def limiter_engine(engine: AsyncEngine) -> AsyncIterator[AsyncEngine]:
    # The limiter commits in its own transaction; clean its exempt table around each test.
    async with engine.begin() as connection:
        await connection.execute(text("DELETE FROM rate_limit_counters"))
    yield engine
    async with engine.begin() as connection:
        await connection.execute(text("DELETE FROM rate_limit_counters"))


async def test_limit_reached_then_resets_next_window(limiter_engine: AsyncEngine) -> None:
    clock = FakeClock(NOW + timedelta(seconds=10))
    limiter = PostgresRateLimiter(limiter_engine, clock)
    bucket = bucket_key("signup", "ip", "203.0.113.7")

    decisions = [await limiter.hit(bucket, limit=3, window_seconds=60) for _ in range(4)]

    assert [d.allowed for d in decisions] == [True, True, True, False]
    assert decisions[-1].retry_after_seconds == 50

    clock.current = NOW + timedelta(seconds=61)
    assert (await limiter.hit(bucket, limit=3, window_seconds=60)).allowed


async def test_buckets_are_independent(limiter_engine: AsyncEngine) -> None:
    limiter = PostgresRateLimiter(limiter_engine, FakeClock(NOW))
    first = bucket_key("signup", "email", "a@example.com")
    second = bucket_key("signup", "email", "b@example.com")

    assert (await limiter.hit(first, limit=1, window_seconds=60)).allowed
    assert not (await limiter.hit(first, limit=1, window_seconds=60)).allowed
    assert (await limiter.hit(second, limit=1, window_seconds=60)).allowed


async def test_raw_ip_and_email_are_not_stored(limiter_engine: AsyncEngine) -> None:
    limiter = PostgresRateLimiter(limiter_engine, FakeClock(NOW))
    await limiter.hit(bucket_key("signup", "ip", "203.0.113.7"), limit=5, window_seconds=60)
    await limiter.hit(bucket_key("signup", "email", "Doc@Example.com"), limit=5, window_seconds=60)

    async with limiter_engine.connect() as connection:
        buckets = (await connection.execute(text("SELECT bucket FROM rate_limit_counters"))).all()
    stored = " ".join(row[0] for row in buckets)
    assert "203.0.113.7" not in stored
    assert "doc@example.com" not in stored.lower()
    assert all(b[0].startswith("signup:") for b in buckets)


async def test_old_windows_are_purged(limiter_engine: AsyncEngine) -> None:
    clock = FakeClock(NOW - timedelta(days=2))
    limiter = PostgresRateLimiter(limiter_engine, clock)
    await limiter.hit("signup:ip:old", limit=5, window_seconds=60)
    clock.current = NOW
    await limiter.hit("signup:ip:new", limit=5, window_seconds=60)

    await limiter.purge()

    async with limiter_engine.connect() as connection:
        buckets = (await connection.execute(text("SELECT bucket FROM rate_limit_counters"))).all()
    assert [b[0] for b in buckets] == ["signup:ip:new"]
