import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.domain.accounts.passwords import check_password_policy
from app.domain.accounts.values import parse_email, parse_ph_mobile, parse_prc_license
from app.domain.errors import (
    FieldConflictError,
    InvalidTokenError,
    RateLimitedError,
    TokenExpiredError,
)

# --- Mobile -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0917 123 4567", "+639171234567"),
        ("09171234567", "+639171234567"),
        ("639171234567", "+639171234567"),
        ("+639171234567", "+639171234567"),
        (" +63-917-123-4567 ", "+639171234567"),
    ],
)
def test_ph_mobile_accepted_and_normalized(raw: str, expected: str) -> None:
    assert parse_ph_mobile(raw) == expected


@pytest.mark.parametrize(
    "raw", ["+14155550100", "0917123", "08171234567", "091712345678", "+63 2 8123 4567", ""]
)
def test_ph_mobile_rejected(raw: str) -> None:
    with pytest.raises(ValueError, match="Philippine mobile"):
        parse_ph_mobile(raw)


# --- PRC license -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("12345", "0012345"), ("0012345", "0012345"), ("1234567", "1234567"), (" 1 ", "0000001")],
)
def test_prc_license_normalized(raw: str, expected: str) -> None:
    assert parse_prc_license(raw) == expected


@pytest.mark.parametrize("raw", ["AB12345", "12345678", "", "12 345", "-12345"])
def test_prc_license_rejected(raw: str) -> None:
    with pytest.raises(ValueError, match="1 to 7 digits"):
        parse_prc_license(raw)


# --- Email -------------------------------------------------------------------------------


def test_email_lowercased() -> None:
    assert parse_email("Juan.DelaCruz@Example.COM") == "juan.delacruz@example.com"


@pytest.mark.parametrize("raw", ["not-an-email", "a@", "@example.com", "a b@example.com"])
def test_email_rejected(raw: str) -> None:
    with pytest.raises(ValueError, match="valid email"):
        parse_email(raw)


def test_email_too_long_rejected() -> None:
    with pytest.raises(ValueError, match="254"):
        parse_email("a" * 250 + "@example.com")


# --- Password policy ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("password", "message"),
    [
        ("a" * 11, "at least 12"),
        ("a" * 129, "at most 128"),
        ("password1234", "too common"),
        ("PASSWORD1234", "too common"),
        ("a" * 12, "too common"),
        ("doc.juan@example.com", "email"),
    ],
)
def test_password_rejected(password: str, message: str) -> None:
    with pytest.raises(ValueError, match=message) as exc_info:
        check_password_policy(password, email="Doc.Juan@example.com")
    assert password not in str(exc_info.value)


@pytest.mark.parametrize(
    "password",
    ["correct horse battery staple", "kalamansi-juice-42", "Mabuhay ang Pilipinas 2026"],
)
def test_password_accepted(password: str) -> None:
    check_password_policy(password, email="doc@example.com")


def test_password_length_counts_normalized_characters() -> None:
    # Eleven full-width letters (U+FF41..) normalize (NFKC) to eleven ASCII ones: still too short.
    full_width = "".join(chr(0xFF41 + i) for i in range(11))
    with pytest.raises(ValueError, match="at least 12"):
        check_password_policy(full_width)


# --- Errors -> HTTP ----------------------------------------------------------------------


async def test_token_errors_and_conflicts_map_to_envelopes(
    app: FastAPI, client: AsyncClient
) -> None:
    @app.get("/api/v1/_test/invalid-token")
    async def invalid() -> None:
        raise InvalidTokenError

    @app.get("/api/v1/_test/expired-token")
    async def expired() -> None:
        raise TokenExpiredError

    @app.get("/api/v1/_test/mobile-conflict")
    async def conflict() -> None:
        raise FieldConflictError("mobile")

    response = await client.get("/api/v1/_test/invalid-token")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_token"

    response = await client.get("/api/v1/_test/expired-token")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "token_expired"

    response = await client.get("/api/v1/_test/mobile-conflict")
    assert response.status_code == 409
    assert response.json()["error"]["details"] == {"field": "mobile"}


async def test_rate_limited_returns_429_with_retry_after(app: FastAPI, client: AsyncClient) -> None:
    @app.get("/api/v1/_test/limited")
    async def limited() -> None:
        raise RateLimitedError(retry_after_seconds=120)

    response = await client.get("/api/v1/_test/limited")
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "120"
    assert response.json()["error"]["code"] == "too_many_requests"
