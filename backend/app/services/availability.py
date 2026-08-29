from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Booking, BookingStatus, Practitioner, ScheduleException, Tenant, WeeklyHours


def _aware(dt: datetime, tz: ZoneInfo) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt.astimezone(tz)


def generate_slots(db: Session, practitioner: Practitioner, day: date) -> list[datetime]:
    tenant = db.get(Tenant, practitioner.tenant_id)
    assert tenant is not None
    tz = ZoneInfo(tenant.timezone)
    weekday = day.weekday()
    hours = db.scalars(
        select(WeeklyHours).where(
            WeeklyHours.practitioner_id == practitioner.id,
            WeeklyHours.weekday == weekday,
        )
    ).all()
    closed = db.scalars(
        select(ScheduleException).where(
            ScheduleException.practitioner_id == practitioner.id,
            ScheduleException.closed_on == day,
        )
    ).first()
    if closed:
        return []

    blocks = db.scalars(
        select(ScheduleException).where(
            ScheduleException.practitioner_id == practitioner.id,
            ScheduleException.block_start.is_not(None),
        )
    ).all()

    booked = set(
        db.scalars(
            select(Booking.starts_at).where(
                Booking.practitioner_id == practitioner.id,
                Booking.status == BookingStatus.booked.value,
            )
        ).all()
    )

    booked_utc = {
        (b if b.tzinfo else b.replace(tzinfo=timezone.utc)).astimezone(timezone.utc) for b in booked
    }

    now = datetime.now(timezone.utc)
    step = timedelta(minutes=settings.slot_minutes)
    # Overlapping or duplicate weekly-hours rows must not offer the same time twice.
    slots: set[datetime] = set()
    for block in hours:
        start_local = datetime.combine(day, block.start_time, tzinfo=tz)
        end_local = datetime.combine(day, block.end_time, tzinfo=tz)
        cursor = start_local
        while cursor + step <= end_local:
            if cursor.astimezone(timezone.utc) <= now:
                cursor += step
                continue
            overlap = False
            for ex in blocks:
                if ex.block_start is None or ex.block_end is None:
                    continue
                bs = _aware(ex.block_start, tz)
                be = _aware(ex.block_end, tz)
                if cursor < be and (cursor + step) > bs:
                    overlap = True
                    break
            if not overlap and cursor.astimezone(timezone.utc) not in booked_utc:
                slots.add(cursor)
            cursor += step
    return sorted(slots)


def dates_with_slots(db: Session, practitioner: Practitioner, start: date, end: date) -> list[date]:
    open_days: list[date] = []
    cursor = start
    while cursor <= end:
        if generate_slots(db, practitioner, cursor):
            open_days.append(cursor)
        cursor += timedelta(days=1)
    return open_days
