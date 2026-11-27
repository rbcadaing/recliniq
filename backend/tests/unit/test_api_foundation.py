"""Request IDs, error envelope, CORS, and OpenAPI behaviour."""

import logging

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from pydantic import BaseModel

from app.domain.errors import ConflictError, NotFoundError


def _assert_envelope(body: dict[str, object], code: str) -> dict[str, object]:
    assert set(body) == {"error"}
    error = body["error"]
    assert isinstance(error, dict)
    assert set(error) == {"code", "message", "details", "request_id"}
    assert error["code"] == code
    assert isinstance(error["message"], str)
    return error


# --- request correlation -------------------------------------------------------------


async def test_supplied_request_id_is_echoed(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health", headers={"X-Request-ID": "abc-123"})
    assert response.headers["X-Request-ID"] == "abc-123"


async def test_request_id_generated_when_missing(client: AsyncClient) -> None:
    first = await client.get("/api/v1/health")
    second = await client.get("/api/v1/health")
    assert first.headers["X-Request-ID"]
    assert first.headers["X-Request-ID"] != second.headers["X-Request-ID"]


async def test_unsafe_request_id_is_replaced(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health", headers={"X-Request-ID": "bad id\twith junk"})
    assert response.headers["X-Request-ID"] != "bad id\twith junk"


async def test_request_is_access_logged(
    client: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="app.access"):
        await client.get("/api/v1/health?token=secret", headers={"X-Request-ID": "log-1"})
    record = next(r for r in caplog.records if r.name == "app.access")
    event = record.msg
    assert isinstance(event, dict)
    assert event["method"] == "GET"
    assert event["path"] == "/api/v1/health"
    assert event["status_code"] == 200
    assert "duration_ms" in event
    assert event["request_id"] == "log-1"
    assert "secret" not in str(event)


# --- error envelope ------------------------------------------------------------------


async def test_unknown_route_returns_404_envelope(client: AsyncClient) -> None:
    response = await client.get("/api/v1/does-not-exist", headers={"X-Request-ID": "nf-1"})
    assert response.status_code == 404
    error = _assert_envelope(response.json(), "not_found")
    assert error["request_id"] == "nf-1"


class _Payload(BaseModel):
    name: str
    age: int


async def test_validation_error_returns_422_with_field_details(
    app: FastAPI, client: AsyncClient
) -> None:
    @app.post("/api/v1/_test/validate")
    async def validate(payload: _Payload) -> dict[str, str]:
        return {"ok": payload.name}

    response = await client.post("/api/v1/_test/validate", json={"name": "x", "age": "old"})
    assert response.status_code == 422
    error = _assert_envelope(response.json(), "validation_error")
    details = error["details"]
    assert isinstance(details, list)
    assert any(item["field"] == "body.age" for item in details)


async def test_app_errors_map_to_status_codes(app: FastAPI, client: AsyncClient) -> None:
    @app.get("/api/v1/_test/missing")
    async def missing() -> None:
        raise NotFoundError("Patient not found.")

    @app.get("/api/v1/_test/conflict")
    async def conflict() -> None:
        raise ConflictError()

    missing_response = await client.get("/api/v1/_test/missing")
    assert missing_response.status_code == 404
    assert _assert_envelope(missing_response.json(), "not_found")["message"] == "Patient not found."

    conflict_response = await client.get("/api/v1/_test/conflict")
    assert conflict_response.status_code == 409
    _assert_envelope(conflict_response.json(), "conflict")


async def test_unexpected_error_returns_generic_500(app: FastAPI, client: AsyncClient) -> None:
    @app.get("/api/v1/_test/boom")
    async def boom() -> None:
        raise RuntimeError("internal detail: password=hunter2")

    response = await client.get("/api/v1/_test/boom", headers={"X-Request-ID": "boom-1"})
    assert response.status_code == 500
    error = _assert_envelope(response.json(), "internal_error")
    assert error["request_id"] == "boom-1"
    assert response.headers["X-Request-ID"] == "boom-1"
    assert "hunter2" not in response.text
    assert "Traceback" not in response.text


# --- CORS ----------------------------------------------------------------------------


async def test_cors_allows_configured_origin(client: AsyncClient) -> None:
    response = await client.options(
        "/api/v1/health",
        headers={"Origin": "http://allowed.test", "Access-Control-Request-Method": "GET"},
    )
    assert response.headers.get("access-control-allow-origin") == "http://allowed.test"


async def test_cors_rejects_unknown_origin(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health", headers={"Origin": "http://evil.test"})
    assert "access-control-allow-origin" not in response.headers


# --- OpenAPI -------------------------------------------------------------------------


async def test_openapi_document_lists_v1_endpoints(client: AsyncClient) -> None:
    response = await client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    document = response.json()
    assert document["openapi"].startswith("3.")
    assert "/api/v1/health" in document["paths"]
    assert "/api/v1/health/ready" in document["paths"]
    assert all(path.startswith("/api/v1/") for path in document["paths"])


async def test_openapi_documents_account_endpoints(client: AsyncClient) -> None:
    document = (await client.get("/api/v1/openapi.json")).json()
    paths = document["paths"]

    assert "get" in paths["/api/v1/specializations"]
    signup = paths["/api/v1/auth/doctors/signup"]["post"]
    assert set(signup["responses"]) >= {"202", "409", "422", "429"}
    body_ref = signup["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    body = document["components"]["schemas"][body_ref.rsplit("/", 1)[-1]]
    assert set(body["required"]) >= {
        "first_name",
        "last_name",
        "email",
        "mobile",
        "password",
        "specialization_id",
        "prc_license_no",
        "privacy_consent",
    }
    assert body["properties"]["password"]["format"] == "password"

    confirm = paths["/api/v1/auth/email-verification/confirm"]["post"]
    assert set(confirm["responses"]) >= {"200", "400", "422"}
    resend = paths["/api/v1/auth/email-verification/resend"]["post"]
    assert set(resend["responses"]) >= {"202", "422", "429"}
