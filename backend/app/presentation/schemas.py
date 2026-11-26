"""Shared API schemas."""

from typing import Any

from pydantic import BaseModel


class ErrorBody(BaseModel):
    code: str
    message: str
    details: Any = None
    request_id: str | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorBody
