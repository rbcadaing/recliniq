"""Map every error to the standard envelope: {"error": {code, message, details, request_id}}."""

from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.middleware import REQUEST_ID_HEADER
from app.domain.errors import (
    AppError,
    ConflictError,
    DependencyUnavailableError,
    DomainValidationError,
    InvalidTokenError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitedError,
    TokenExpiredError,
)

logger = structlog.get_logger("app.errors")

_STATUS_BY_ERROR: dict[type[AppError], int] = {
    NotFoundError: 404,
    ConflictError: 409,
    DomainValidationError: 422,
    PermissionDeniedError: 403,
    DependencyUnavailableError: 503,
    InvalidTokenError: 400,
    TokenExpiredError: 400,
    RateLimitedError: 429,
}

_CODE_BY_STATUS: dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    403: "permission_denied",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "validation_error",
    429: "too_many_requests",
    503: "service_unavailable",
}


def error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    body = {
        "error": {
            "code": code,
            "message": message,
            "details": jsonable_encoder(details),
            "request_id": request_id,
        }
    }
    response_headers = dict(headers or {})
    if request_id:
        response_headers[REQUEST_ID_HEADER] = request_id
    return JSONResponse(status_code=status_code, content=body, headers=response_headers)


def _status_for(exc: AppError) -> int:
    for cls in type(exc).__mro__:
        if cls in _STATUS_BY_ERROR:
            return _STATUS_BY_ERROR[cls]
    return 400


async def handle_app_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)  # noqa: S101
    headers = None
    if isinstance(exc, RateLimitedError):
        headers = {"Retry-After": str(exc.retry_after_seconds)}
    return error_response(
        request,
        status_code=_status_for(exc),
        code=exc.code,
        message=exc.message,
        details=exc.details,
        headers=headers,
    )


async def handle_http_exception(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)  # noqa: S101
    message = exc.detail if isinstance(exc.detail, str) else "Request failed."
    return error_response(
        request,
        status_code=exc.status_code,
        code=_CODE_BY_STATUS.get(exc.status_code, "http_error"),
        message=message,
        headers=dict(exc.headers) if exc.headers else None,
    )


async def handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)  # noqa: S101
    details = [
        {
            "field": ".".join(str(part) for part in err.get("loc", ())),
            "message": err.get("msg"),
            "type": err.get("type"),
        }
        for err in exc.errors()
    ]
    return error_response(
        request,
        status_code=422,
        code="validation_error",
        message="The request is invalid.",
        details=details,
    )


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled_exception", exc_type=type(exc).__name__)
    return error_response(
        request,
        status_code=500,
        code="internal_error",
        message="An unexpected error occurred.",
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, handle_app_error)
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(Exception, handle_unexpected_error)
