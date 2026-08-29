from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_staff
from app.models import Practitioner, ScheduleException, User, WeeklyHours
from app.schemas import ExceptionIn, ExceptionOut, PractitionerOut, SlotOut, WeeklyHoursIn, WeeklyHoursOut
from app.services.availability import dates_with_slots, generate_slots

router = APIRouter(tags=["schedule"])


def _practitioner(db: Session, tenant_id: int, practitioner_id: int) -> Practitioner:
    p = db.get(Practitioner, practitioner_id)
    if p is None or p.tenant_id != tenant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    return p


@router.get("/practitioners", response_model=list[PractitionerOut])
def list_practitioners(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[Practitioner]:
    return list(db.scalars(select(Practitioner).where(Practitioner.tenant_id == user.tenant_id)))


@router.get("/patients", response_model=list)
def list_patients(
    staff: Annotated[User, Depends(require_staff)],
    db: Annotated[Session, Depends(get_db)],
):
    rows = db.scalars(
        select(User).where(User.tenant_id == staff.tenant_id, User.role == "patient")
    ).all()
    return [{"id": u.id, "email": u.email, "display_name": u.display_name, "role": u.role} for u in rows]


@router.get("/practitioners/{practitioner_id}/availability", response_model=list[SlotOut])
def availability(
    practitioner_id: int,
    date: date,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[SlotOut]:
    p = _practitioner(db, user.tenant_id, practitioner_id)
    return [SlotOut(starts_at=s) for s in generate_slots(db, p, date)]


@router.get("/practitioners/{practitioner_id}/available-dates", response_model=list[date])
def available_dates(
    practitioner_id: int,
    start: date,
    end: date,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[date]:
    if end < start:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="end must be on or after start")
    if (end - start).days > 62:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Range cannot exceed 62 days")
    p = _practitioner(db, user.tenant_id, practitioner_id)
    return dates_with_slots(db, p, start, end)


@router.get("/practitioners/{practitioner_id}/hours", response_model=list[WeeklyHoursOut])
def list_hours(
    practitioner_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[WeeklyHours]:
    _practitioner(db, user.tenant_id, practitioner_id)
    return list(
        db.scalars(select(WeeklyHours).where(WeeklyHours.practitioner_id == practitioner_id))
    )


@router.post("/hours", response_model=WeeklyHoursOut)
def create_hours(
    body: WeeklyHoursIn,
    staff: Annotated[User, Depends(require_staff)],
    db: Annotated[Session, Depends(get_db)],
) -> WeeklyHours:
    _practitioner(db, staff.tenant_id, body.practitioner_id)
    if body.end_time <= body.start_time:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid hours")
    row = WeeklyHours(
        tenant_id=staff.tenant_id,
        practitioner_id=body.practitioner_id,
        weekday=body.weekday,
        start_time=body.start_time,
        end_time=body.end_time,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/hours/{hours_id}", status_code=204)
def delete_hours(
    hours_id: int,
    staff: Annotated[User, Depends(require_staff)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    row = db.get(WeeklyHours, hours_id)
    if row is None or row.tenant_id != staff.tenant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    db.delete(row)
    db.commit()


@router.get("/practitioners/{practitioner_id}/exceptions", response_model=list[ExceptionOut])
def list_exceptions(
    practitioner_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[ScheduleException]:
    _practitioner(db, user.tenant_id, practitioner_id)
    return list(
        db.scalars(select(ScheduleException).where(ScheduleException.practitioner_id == practitioner_id))
    )


@router.post("/exceptions", response_model=ExceptionOut)
def create_exception(
    body: ExceptionIn,
    staff: Annotated[User, Depends(require_staff)],
    db: Annotated[Session, Depends(get_db)],
) -> ScheduleException:
    _practitioner(db, staff.tenant_id, body.practitioner_id)
    row = ScheduleException(
        tenant_id=staff.tenant_id,
        practitioner_id=body.practitioner_id,
        closed_on=body.closed_on,
        block_start=body.block_start,
        block_end=body.block_end,
        reason=body.reason,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/exceptions/{exception_id}", status_code=204)
def delete_exception(
    exception_id: int,
    staff: Annotated[User, Depends(require_staff)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    row = db.get(ScheduleException, exception_id)
    if row is None or row.tenant_id != staff.tenant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    db.delete(row)
    db.commit()
