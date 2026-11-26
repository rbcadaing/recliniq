"""Integration fixtures. Require TEST_DATABASE_URL pointing at a disposable PostgreSQL database.

The schema is migrated once per session; each test gets a session inside a transaction that
is rolled back afterwards, so tests never see each other's data.
"""

import os
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from alembic import command
from app.core.config import load_settings
from app.main import create_app

BACKEND_DIR = Path(__file__).resolve().parents[2]


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if "tests/integration" in item.nodeid.replace("\\", "/"):
            item.add_marker(pytest.mark.integration)
            if not os.environ.get("TEST_DATABASE_URL"):
                item.add_marker(pytest.mark.skip(reason="TEST_DATABASE_URL not set"))


@pytest.fixture(scope="session")
def test_database_url() -> str:
    return os.environ["TEST_DATABASE_URL"]


def alembic_config(database_url: str) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    config.attributes["configure_logger"] = False
    return config


@pytest.fixture(scope="session")
def migrated_database(test_database_url: str) -> Iterator[str]:
    command.upgrade(alembic_config(test_database_url), "head")
    yield test_database_url


@pytest.fixture(scope="session")
async def engine(migrated_database: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(migrated_database)
    yield engine
    await engine.dispose()


@asynccontextmanager
async def transactional_session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Session whose work (including commits, via savepoints) is rolled back on exit."""
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


@pytest.fixture
async def db_session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with transactional_session(engine) as session:
        yield session


@pytest.fixture
def integration_app(migrated_database: str) -> FastAPI:
    settings = load_settings(_env_file=None, app_env="test", database_url=migrated_database)
    return create_app(settings)


@pytest.fixture
async def integration_client(integration_app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=integration_app)
    async with (
        integration_app.router.lifespan_context(integration_app),
        AsyncClient(transport=transport, base_url="http://testserver") as http,
    ):
        yield http
