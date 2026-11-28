"""Fixed-window rate limiter backed by the ``rate_limit_counters`` table."""

import math
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from app.application.accounts.ports import Clock, RateLimitDecision
from app.infrastructure.accounts.models import RateLimitCounterModel
from app.infrastructure.clock import SystemClock

PURGE_PROBABILITY_PERCENT = 1
PURGE_OLDER_THAN = timedelta(days=1)


class PostgresRateLimiter:
    """Counts in its own committed transaction, so attempts count even when a request fails."""

    def __init__(self, engine: AsyncEngine, clock: Clock | None = None) -> None:
        self._engine = engine
        self._clock = clock or SystemClock()

    async def hit(self, bucket: str, *, limit: int, window_seconds: int) -> RateLimitDecision:
        now = self._clock.now()
        epoch = now.timestamp()
        window_start = datetime.fromtimestamp(epoch - epoch % window_seconds, tz=UTC)
        retry_after = max(1, math.ceil(window_start.timestamp() + window_seconds - epoch))

        statement = (
            insert(RateLimitCounterModel)
            .values(bucket=bucket, window_start=window_start, count=1)
            .on_conflict_do_update(
                index_elements=["bucket", "window_start"],
                set_={"count": RateLimitCounterModel.count + 1},
            )
            .returning(RateLimitCounterModel.count)
        )
        async with self._engine.begin() as connection:
            count = (await connection.execute(statement)).scalar_one()
            if secrets.randbelow(100) < PURGE_PROBABILITY_PERCENT:
                await self._purge(connection, now)

        if count > limit:
            return RateLimitDecision(allowed=False, retry_after_seconds=retry_after)
        return RateLimitDecision(allowed=True)

    @staticmethod
    async def _purge(connection: AsyncConnection, now: datetime) -> None:
        await connection.execute(
            # hard-delete-ok: rate_limit_counters is exempt from soft delete (expired windows)
            delete(RateLimitCounterModel).where(
                RateLimitCounterModel.window_start < now - PURGE_OLDER_THAN
            )
        )

    async def purge(self) -> None:
        """Delete windows older than a day. Exposed for tests and maintenance."""
        async with self._engine.begin() as connection:
            await self._purge(connection, self._clock.now())
