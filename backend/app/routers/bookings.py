from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_staff
from app.models import Booking, User
from app.schemas import BookingIn, BookingOut, CancelIn, OnBehalfBookingIn
from app.services.booking import BookingConflict, BookingError, cancel_booking, create_booking

router = APIRouter(prefix="/bookings", tags=["bookings"])


def _out(booking: Booking) -> BookingOut:
    return BookingOut(
        id=booking.id,
        practitioner_id=booking.practitioner_id,
        patient_id=booking.patient_id,
        starts_at=booking.starts_at,
        status=booking.status,
        created_by_user_id=booking.created_by_user_id,
        cancelled_by_user_id=booking.cancelled_by_user_id,
        cancelled_at=booking.cancelled_at,
        cancel_reason=booking.cancel_reason,
        visit_record_id=booking.visit_record.id if booking.visit_record else None,
    )


@router.get("", response_model=list[BookingOut])
def list_bookings(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    patient_id: int | None = None,
) -> list[BookingOut]:
    q = select(Booking).where(Booking.tenant_id == user.tenant_id)
    if user.role == "patient":
        q = q.where(Booking.patient_id == user.id)
    elif patient_id is not None:
        q = q.where(Booking.patient_id == patient_id)
    rows = db.scalars(q.order_by(Booking.starts_at.desc())).all()
    return [_out(b) for b in rows]


@router.post("", response_model=BookingOut)
def book_self(
    body: BookingIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> BookingOut:
    if user.role != "patient":
        raise HTTPException(403, detail="Patients book themselves; staff use on-behalf")
    try:
        booking = create_booking(
            db, actor=user, patient=user, practitioner_id=body.practitioner_id, starts_at=body.starts_at
        )
    except BookingConflict:
        raise HTTPException(409, detail="Slot no longer available") from None
    except BookingError as exc:
        raise HTTPException(exc.status_code, detail=exc.detail) from None
    return _out(booking)


@router.post("/on-behalf", response_model=BookingOut)
def book_on_behalf(
    body: OnBehalfBookingIn,
    staff: Annotated[User, Depends(require_staff)],
    db: Annotated[Session, Depends(get_db)],
) -> BookingOut:
    patient = db.get(User, body.patient_id)
    if patient is None or patient.tenant_id != staff.tenant_id or patient.role != "patient":
        raise HTTPException(404, detail="Not found")
    try:
        booking = create_booking(
            db,
            actor=staff,
            patient=patient,
            practitioner_id=body.practitioner_id,
            starts_at=body.starts_at,
        )
    except BookingConflict:
        raise HTTPException(409, detail="Slot no longer available") from None
    except BookingError as exc:
        raise HTTPException(exc.status_code, detail=exc.detail) from None
    return _out(booking)


@router.post("/{booking_id}/cancel", response_model=BookingOut)
def cancel(
    booking_id: int,
    body: CancelIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> BookingOut:
    try:
        booking = cancel_booking(db, user, booking_id, body.reason)
    except BookingError as exc:
        raise HTTPException(exc.status_code, detail=exc.detail) from None
    return _out(booking)
