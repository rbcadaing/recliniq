from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import InAppAlert, User
from app.schemas import AlertOut
from app.services.email_outbox import process_outbox

router = APIRouter(tags=["alerts"])


@router.get("/alerts", response_model=list[AlertOut])
def list_alerts(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[InAppAlert]:
    return list(
        db.scalars(
            select(InAppAlert)
            .where(InAppAlert.user_id == user.id, InAppAlert.tenant_id == user.tenant_id)
            .order_by(InAppAlert.created_at.desc())
        )
    )


@router.post("/alerts/{alert_id}/read", response_model=AlertOut)
def mark_read(
    alert_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> InAppAlert:
    row = db.get(InAppAlert, alert_id)
    if row is None or row.user_id != user.id or row.tenant_id != user.tenant_id:
        raise HTTPException(404, detail="Not found")
    row.read_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return row


@router.post("/internal/run-outbox")
def run_outbox(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    if user.role not in ("doctor", "assistant"):
        raise HTTPException(403, detail="Staff only")
    n = process_outbox(db)
    return {"sent": n}
