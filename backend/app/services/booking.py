from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Booking,
    BookingStatus,
    Practitioner,
    User,
    VisitRecord,
)
from app.services.notify import emit_event


class BookingConflict(Exception):
    pass


class BookingError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail


def _get_practitioner(db: Session, tenant_id: int, practitioner_id: int) -> Practitioner:
    p = db.get(Practitioner, practitioner_id)
    if p is None or p.tenant_id != tenant_id:
        raise BookingError(404, "Not found")
    return p


def create_booking(
    db: Session,
    *,
    actor: User,
    patient: User,
    practitioner_id: int,
    starts_at: datetime,
) -> Booking:
    if patient.tenant_id != actor.tenant_id:
        raise BookingError(404, "Not found")
    practitioner = _get_practitioner(db, actor.tenant_id, practitioner_id)
    if starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=timezone.utc)
    starts_at = starts_at.astimezone(timezone.utc)
    now = datetime.now(timezone.utc)
    if starts_at < now:
        raise BookingError(400, "Cannot book in the past")

    taken = db.scalars(
        select(Booking).where(
            Booking.practitioner_id == practitioner.id,
            Booking.starts_at == starts_at,
            Booking.status == BookingStatus.booked.value,
        )
    ).first()
    if taken:
        raise BookingConflict()

    booking = Booking(
        tenant_id=actor.tenant_id,
        practitioner_id=practitioner.id,
        patient_id=patient.id,
        starts_at=starts_at,
        status=BookingStatus.booked.value,
        created_by_user_id=actor.id,
    )
    record = VisitRecord(tenant_id=actor.tenant_id, booking=booking, notes="")
    db.add(booking)
    db.add(record)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise BookingConflict from exc

    emit_event(
        db,
        tenant_id=actor.tenant_id,
        patient=patient,
        practitioner=practitioner,
        event_type="booking.created",
        body=f"Consultation booked at {starts_at.isoformat()} (created by {actor.role})",
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise BookingConflict from exc
    db.refresh(booking)
    db.refresh(record)
    booking.visit_record = record
    return booking


def cancel_booking(db: Session, actor: User, booking_id: int, reason: str | None) -> Booking:
    booking = db.get(Booking, booking_id)
    if booking is None or booking.tenant_id != actor.tenant_id:
        raise BookingError(404, "Not found")
    if actor.role == "patient" and booking.patient_id != actor.id:
        raise BookingError(404, "Not found")
    if booking.status == BookingStatus.cancelled.value:
        raise BookingError(409, "Already cancelled")
    booking.status = BookingStatus.cancelled.value
    booking.cancelled_by_user_id = actor.id
    booking.cancelled_at = datetime.now(timezone.utc)
    booking.cancel_reason = reason
    patient = db.get(User, booking.patient_id)
    practitioner = db.get(Practitioner, booking.practitioner_id)
    assert patient and practitioner
    emit_event(
        db,
        tenant_id=actor.tenant_id,
        patient=patient,
        practitioner=practitioner,
        event_type="booking.cancelled",
        body=f"Booking cancelled by {actor.role}. Reason: {reason or '(none)'}",
    )
    db.commit()
    db.refresh(booking)
    return booking
