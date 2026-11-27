"""Integration fixtures. Require TEST_DATABASE_URL pointing at a disposable PostgreSQL database.

The schema is migrated once per session; each test gets a session inside a transaction that
is rolled back afterwards, so tests never see each other's data.
"""

import os
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from alembic import command
from app.core.config import load_settings
from app.infrastructure.accounts.mailer import InMemoryMailer
from app.main import create_app
from app.presentation.dependencies import get_clock, get_mailer, get_session
from tests.integration.api_support import PASSWORD, FakeClock

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


# --- Account API fixtures (shared by the account and session API tests) -----------------


@pytest.fixture
async def clean_rate_limits(engine: AsyncEngine) -> AsyncIterator[None]:
    async with engine.begin() as connection:
        await connection.execute(text("DELETE FROM rate_limit_counters"))
    yield
    async with engine.begin() as connection:
        await connection.execute(text("DELETE FROM rate_limit_counters"))


@pytest.fixture
def mailer() -> InMemoryMailer:
    return InMemoryMailer()


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
async def api(
    integration_app: FastAPI,
    db_session: AsyncSession,
    mailer: InMemoryMailer,
    clock: FakeClock,
    clean_rate_limits: None,
) -> AsyncIterator[Callable[..., AsyncClient]]:
    async def shared_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    integration_app.dependency_overrides[get_session] = shared_session
    integration_app.dependency_overrides[get_mailer] = lambda: mailer
    integration_app.dependency_overrides[get_clock] = lambda: clock
    clients: list[AsyncClient] = []

    def make(ip: str = "203.0.113.10") -> AsyncClient:
        transport = ASGITransport(app=integration_app, client=(ip, 50000))
        client = AsyncClient(transport=transport, base_url="http://testserver")
        clients.append(client)
        return client

    async with integration_app.router.lifespan_context(integration_app):
        yield make
        for client in clients:
            await client.aclose()


@pytest.fixture
async def client(api: Callable[..., AsyncClient]) -> AsyncClient:
    return api()


@pytest.fixture
async def specialization_id(client: AsyncClient) -> str:
    response = await client.get("/api/v1/specializations")
    return str(response.json()[0]["id"])


@pytest.fixture
def signup(specialization_id: str) -> Callable[..., dict[str, Any]]:
    def build(**overrides: Any) -> dict[str, Any]:
        body: dict[str, Any] = {
            "first_name": "Juan",
            "middle_name": "Santos",
            "last_name": "Dela Cruz",
            "email": "Juan.DelaCruz@Example.com",
            "mobile": "0917 123 4567",
            "password": PASSWORD,
            "specialization_id": specialization_id,
            "prc_license_no": "12345",
            "privacy_consent": True,
        }
        body.update(overrides)
        return body

    return build
