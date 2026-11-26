from fastapi import APIRouter
from pydantic import BaseModel

from app.presentation.dependencies import DatabaseHealthCheckDep, HealthServiceDep
from app.presentation.schemas import ErrorEnvelope

router = APIRouter(prefix="/health", tags=["health"])


class LivenessResponse(BaseModel):
    status: str
    name: str
    version: str


class ReadinessResponse(BaseModel):
    status: str
    checks: dict[str, str]


@router.get("", response_model=LivenessResponse, summary="Liveness check")
async def liveness(service: HealthServiceDep) -> LivenessResponse:
    result = service.liveness()
    return LivenessResponse(status=result.status, name=result.name, version=result.version)


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Readiness check (database connectivity)",
    responses={503: {"model": ErrorEnvelope, "description": "A dependency is unavailable"}},
)
async def readiness(
    service: HealthServiceDep, database: DatabaseHealthCheckDep
) -> ReadinessResponse:
    result = await service.readiness(database)
    return ReadinessResponse(status=result.status, checks=result.checks)
