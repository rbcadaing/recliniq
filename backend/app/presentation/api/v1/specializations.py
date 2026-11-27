import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from app.presentation.dependencies import SpecializationRepositoryDep

router = APIRouter(prefix="/specializations", tags=["specializations"])


class SpecializationResponse(BaseModel):
    id: uuid.UUID
    code: str
    name: str


@router.get("", response_model=list[SpecializationResponse], summary="List specializations")
async def list_specializations(
    repository: SpecializationRepositoryDep,
) -> list[SpecializationResponse]:
    return [
        SpecializationResponse(id=s.id, code=s.code, name=s.name)
        for s in await repository.list_all()
    ]
