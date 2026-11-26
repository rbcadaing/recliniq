from fastapi import FastAPI
from httpx import AsyncClient

from app.presentation.dependencies import get_database_health_check

UNIT_DB_PASSWORD = "test"  # matches UNIT_DATABASE_URL in conftest


class _HealthyDatabase:
    async def ping(self) -> None:
        return None


class _BrokenDatabase:
    async def ping(self) -> None:
        raise ConnectionRefusedError("connect to postgresql+asyncpg://test:test@db failed")


async def test_liveness_returns_status_name_and_version(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "name": "RecliniQ", "version": "0.1.0"}


async def test_readiness_ok_when_database_reachable(app: FastAPI, client: AsyncClient) -> None:
    app.dependency_overrides[get_database_health_check] = _HealthyDatabase
    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"database": "ok"}}


async def test_readiness_503_when_database_down(app: FastAPI, client: AsyncClient) -> None:
    app.dependency_overrides[get_database_health_check] = _BrokenDatabase
    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "service_unavailable"
    assert error["details"] == {"checks": {"database": "failed"}}
    assert "postgresql" not in response.text


async def test_readiness_503_with_real_unreachable_engine(client: AsyncClient) -> None:
    # No override: the real SQLAlchemy health check targets an unroutable port.
    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert "postgresql" not in response.text
    assert UNIT_DB_PASSWORD + "@" not in response.text
