"""Health use cases. Depends only on the ``DatabaseHealthCheck`` port, not on SQLAlchemy."""

from dataclasses import dataclass
from typing import Protocol

from app.domain.errors import DependencyUnavailableError


class DatabaseHealthCheck(Protocol):
    async def ping(self) -> None:
        """Raise any exception if the database cannot be reached."""


@dataclass(frozen=True, slots=True)
class Liveness:
    status: str
    name: str
    version: str


@dataclass(frozen=True, slots=True)
class Readiness:
    status: str
    checks: dict[str, str]


class HealthService:
    def __init__(self, *, app_name: str, app_version: str) -> None:
        self._app_name = app_name
        self._app_version = app_version

    def liveness(self) -> Liveness:
        return Liveness(status="ok", name=self._app_name, version=self._app_version)

    async def readiness(self, database: DatabaseHealthCheck) -> Readiness:
        try:
            await database.ping()
        except Exception as exc:
            raise DependencyUnavailableError(
                "The database is unavailable.", details={"checks": {"database": "failed"}}
            ) from exc
        return Readiness(status="ok", checks={"database": "ok"})
