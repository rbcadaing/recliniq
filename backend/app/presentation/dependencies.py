"""FastAPI dependencies that wire infrastructure into application services."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.health.service import DatabaseHealthCheck, HealthService
from app.core.config import Settings
from app.infrastructure.db.database import Database, SqlDatabaseHealthCheck


def get_app_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_database(request: Request) -> Database:
    database: Database = request.app.state.database
    return database


async def get_session(
    database: Annotated[Database, Depends(get_database)],
) -> AsyncIterator[AsyncSession]:
    async for session in database.session():
        yield session


def get_health_service(
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> HealthService:
    return HealthService(app_name=settings.app_name, app_version=settings.app_version)


def get_database_health_check(
    database: Annotated[Database, Depends(get_database)],
) -> DatabaseHealthCheck:
    return SqlDatabaseHealthCheck(database.engine)


SettingsDep = Annotated[Settings, Depends(get_app_settings)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
HealthServiceDep = Annotated[HealthService, Depends(get_health_service)]
DatabaseHealthCheckDep = Annotated[DatabaseHealthCheck, Depends(get_database_health_check)]
