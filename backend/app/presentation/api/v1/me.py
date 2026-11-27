import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from app.domain.accounts.values import LicenseStatus, Role
from app.domain.errors import NotAuthenticatedError
from app.infrastructure.accounts.repositories import SqlUserRepository
from app.presentation.dependencies import SessionDep
from app.presentation.schemas import ErrorEnvelope
from app.presentation.security import CurrentUserDep

router = APIRouter(prefix="/me", tags=["account"])


class SpecializationRef(BaseModel):
    id: uuid.UUID
    name: str


class DoctorInfo(BaseModel):
    specialization: SpecializationRef
    license_status: LicenseStatus


class AccountProfileResponse(BaseModel):
    id: uuid.UUID
    first_name: str
    middle_name: str | None
    last_name: str
    email: str
    role: Role
    email_verified: bool
    doctor: DoctorInfo | None = None


@router.get(
    "",
    response_model=AccountProfileResponse,
    summary="The signed-in user's profile",
    responses={401: {"model": ErrorEnvelope, "description": "not_authenticated"}},
)
async def get_me(user: CurrentUserDep, session: SessionDep) -> AccountProfileResponse:
    profile = await SqlUserRepository(session).find_profile(user.id)
    if profile is None:
        raise NotAuthenticatedError
    doctor = None
    if profile.doctor is not None:
        doctor = DoctorInfo(
            specialization=SpecializationRef(
                id=profile.doctor.specialization.id, name=profile.doctor.specialization.name
            ),
            license_status=profile.doctor.license_status,
        )
    return AccountProfileResponse(
        id=profile.id,
        first_name=profile.first_name,
        middle_name=profile.middle_name,
        last_name=profile.last_name,
        email=profile.email,
        role=profile.role,
        email_verified=profile.email_verified,
        doctor=doctor,
    )
