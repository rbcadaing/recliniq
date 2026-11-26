from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings, load_settings
from app.main import create_app

# Unit tests never connect: port 1 is unroutable, so anything hitting the DB fails fast.
UNIT_DATABASE_URL = "postgresql+asyncpg://test:test@127.0.0.1:1/test"


@pytest.fixture
def settings() -> Settings:
    return load_settings(
        _env_file=None,
        app_env="test",
        database_url=UNIT_DATABASE_URL,
        cors_origins="http://allowed.test",
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    # raise_app_exceptions=False lets us assert on the 500 response instead of re-raising.
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http:
        yield http
