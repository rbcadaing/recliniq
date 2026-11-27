"""Application factory. Run with: uvicorn app.main:create_app --factory"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.middleware import REQUEST_ID_HEADER, RequestContextMiddleware
from app.infrastructure.db.database import Database
from app.presentation.api.v1.router import api_router
from app.presentation.errors import register_error_handlers
from app.presentation.schemas import ErrorEnvelope


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, json_logs=not settings.is_local)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        await app.state.database.dispose()

    app = FastAPI(
        title=f"{settings.app_name} API",
        version=settings.app_version,
        openapi_url="/api/v1/openapi.json",
        docs_url="/api/v1/docs",
        redoc_url=None,
        lifespan=lifespan,
        responses={422: {"model": ErrorEnvelope}, 500: {"model": ErrorEnvelope}},
    )
    app.state.settings = settings
    # Engine creation is lazy: no connection is opened until the first query.
    app.state.database = Database(
        settings.database_url.get_secret_value(), echo=settings.database_echo
    )

    register_error_handlers(app)

    # Middleware order: last added runs first. Request context wraps everything.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[REQUEST_ID_HEADER, "Retry-After"],
    )
    app.add_middleware(RequestContextMiddleware)

    app.include_router(api_router)
    return app
