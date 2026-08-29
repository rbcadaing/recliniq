from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Tenant, User, UserRole
from app.schemas import LoginIn, RegisterIn, TokenOut, UserOut
from app.security import create_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _default_tenant(db: Session) -> Tenant:
    tenant = db.scalars(select(Tenant).order_by(Tenant.id)).first()
    if tenant is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="Clinic is not seeded")
    return tenant


@router.post("/register", response_model=TokenOut)
def register(body: RegisterIn, db: Annotated[Session, Depends(get_db)]) -> TokenOut:
    tenant = _default_tenant(db)
    existing = db.scalars(
        select(User).where(User.tenant_id == tenant.id, User.email == str(body.email).lower())
    ).first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Email already registered")
    user = User(
        tenant_id=tenant.id,
        email=str(body.email).lower(),
        password_hash=hash_password(body.password),
        role=UserRole.patient.value,
        display_name=body.display_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenOut(access_token=create_token(user_id=user.id, tenant_id=user.tenant_id, role=user.role))


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Annotated[Session, Depends(get_db)]) -> TokenOut:
    tenant = _default_tenant(db)
    user = db.scalars(
        select(User).where(User.tenant_id == tenant.id, User.email == str(body.email).lower())
    ).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return TokenOut(access_token=create_token(user_id=user.id, tenant_id=user.tenant_id, role=user.role))


@router.get("/me", response_model=UserOut)
def me(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user
