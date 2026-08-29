from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Booking, Practitioner, User, VisitDocument, VisitRecord
from app.schemas import DocumentOut, VisitOut, VisitUpdateIn
from app.services.files import read_stored, save_upload
from app.services.notify import emit_event

router = APIRouter(prefix="/visits", tags=["visits"])


def _can_access(user: User, booking: Booking) -> bool:
    if booking.tenant_id != user.tenant_id:
        return False
    if user.role in ("doctor", "assistant"):
        return True
    return booking.patient_id == user.id


def _visit_out(record: VisitRecord, booking: Booking) -> VisitOut:
    return VisitOut(
        id=record.id,
        booking_id=booking.id,
        notes=record.notes,
        updated_by_user_id=record.updated_by_user_id,
        updated_at=record.updated_at,
        patient_id=booking.patient_id,
        practitioner_id=booking.practitioner_id,
        starts_at=booking.starts_at,
        booking_status=booking.status,
        cancelled_by_user_id=booking.cancelled_by_user_id,
        cancelled_at=booking.cancelled_at,
        cancel_reason=booking.cancel_reason,
    )


def _get_record(db: Session, user: User, visit_id: int) -> tuple[VisitRecord, Booking]:
    record = db.get(VisitRecord, visit_id)
    if record is None or record.tenant_id != user.tenant_id:
        raise HTTPException(404, detail="Not found")
    booking = db.get(Booking, record.booking_id)
    if booking is None or not _can_access(user, booking):
        raise HTTPException(404, detail="Not found")
    return record, booking


@router.get("", response_model=list[VisitOut])
def list_visits(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    patient_id: int | None = None,
) -> list[VisitOut]:
    q = select(VisitRecord).where(VisitRecord.tenant_id == user.tenant_id)
    records = db.scalars(q).all()
    out: list[VisitOut] = []
    for record in records:
        booking = db.get(Booking, record.booking_id)
        if booking is None or not _can_access(user, booking):
            continue
        if user.role == "patient" and booking.patient_id != user.id:
            continue
        if patient_id is not None and booking.patient_id != patient_id:
            continue
        if user.role != "patient" and patient_id is None:
            pass
        out.append(_visit_out(record, booking))
    out.sort(key=lambda v: v.starts_at, reverse=True)
    return out


@router.get("/{visit_id}", response_model=VisitOut)
def get_visit(
    visit_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> VisitOut:
    record, booking = _get_record(db, user, visit_id)
    return _visit_out(record, booking)


@router.patch("/{visit_id}", response_model=VisitOut)
def update_visit(
    visit_id: int,
    body: VisitUpdateIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> VisitOut:
    record, booking = _get_record(db, user, visit_id)
    record.notes = body.notes
    record.updated_by_user_id = user.id
    record.updated_at = datetime.now(timezone.utc)
    patient = db.get(User, booking.patient_id)
    practitioner = db.get(Practitioner, booking.practitioner_id)
    assert patient and practitioner
    emit_event(
        db,
        tenant_id=user.tenant_id,
        patient=patient,
        practitioner=practitioner,
        event_type="visit.updated",
        body=f"Visit record updated by {user.role}",
    )
    db.commit()
    db.refresh(record)
    return _visit_out(record, booking)


@router.get("/{visit_id}/documents", response_model=list[DocumentOut])
def list_docs(
    visit_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[VisitDocument]:
    _get_record(db, user, visit_id)
    return list(db.scalars(select(VisitDocument).where(VisitDocument.visit_record_id == visit_id)))


@router.post("/{visit_id}/documents", response_model=DocumentOut)
def upload_doc(
    visit_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    file: UploadFile = File(...),
) -> VisitDocument:
    record, booking = _get_record(db, user, visit_id)
    filename, stored, content_type, size = save_upload(user.tenant_id, record.id, file)
    doc = VisitDocument(
        tenant_id=user.tenant_id,
        visit_record_id=record.id,
        filename=filename,
        stored_name=stored,
        content_type=content_type,
        size_bytes=size,
        uploaded_by_user_id=user.id,
    )
    db.add(doc)
    patient = db.get(User, booking.patient_id)
    practitioner = db.get(Practitioner, booking.practitioner_id)
    assert patient and practitioner
    emit_event(
        db,
        tenant_id=user.tenant_id,
        patient=patient,
        practitioner=practitioner,
        event_type="visit.document",
        body=f"Document uploaded: {filename}",
    )
    db.commit()
    db.refresh(doc)
    return doc


@router.get("/{visit_id}/documents/{doc_id}")
def download_doc(
    visit_id: int,
    doc_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    _get_record(db, user, visit_id)
    doc = db.get(VisitDocument, doc_id)
    if doc is None or doc.visit_record_id != visit_id or doc.tenant_id != user.tenant_id:
        raise HTTPException(404, detail="Not found")
    data = read_stored(user.tenant_id, visit_id, doc.stored_name)
    return Response(
        content=data,
        media_type=doc.content_type,
        headers={"Content-Disposition": f'attachment; filename="{doc.filename}"'},
    )
