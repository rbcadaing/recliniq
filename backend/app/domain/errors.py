"""Domain-level errors. Framework-free: the presentation layer maps these to HTTP responses."""

from typing import Any


class AppError(Exception):
    """Base class for expected, user-facing application errors."""

    code: str = "app_error"
    message: str = "An application error occurred."

    def __init__(self, message: str | None = None, *, details: Any = None) -> None:
        self.message = message or self.message
        self.details = details
        super().__init__(self.message)


class NotFoundError(AppError):
    code = "not_found"
    message = "The requested resource was not found."


class ConflictError(AppError):
    code = "conflict"
    message = "The request conflicts with the current state of the resource."


class DomainValidationError(AppError):
    code = "validation_error"
    message = "The request is invalid."


class PermissionDeniedError(AppError):
    code = "permission_denied"
    message = "You do not have permission to perform this action."


class FieldConflictError(ConflictError):
    """A unique value is already taken. ``details`` names the field: ``{"field": "mobile"}``."""

    def __init__(self, field: str, message: str | None = None) -> None:
        super().__init__(message or f"This {field.replace('_', ' ')} is already registered.")
        self.details = {"field": field}


class InvalidTokenError(AppError):
    code = "invalid_token"
    message = "This link is invalid or has already been used."


class TokenExpiredError(AppError):
    code = "token_expired"
    message = "This link has expired."


class RateLimitedError(AppError):
    code = "too_many_requests"
    message = "Too many attempts. Please try again later."

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(details={"retry_after_seconds": retry_after_seconds})
        self.retry_after_seconds = retry_after_seconds


class InvalidCredentialsError(AppError):
    code = "invalid_credentials"
    message = "Incorrect email or password."


class EmailNotVerifiedError(AppError):
    code = "email_not_verified"
    message = "Please verify your email address before signing in."


class InvalidRefreshTokenError(AppError):
    code = "invalid_refresh_token"
    message = "Your session has expired. Please sign in again."


class NotAuthenticatedError(AppError):
    code = "not_authenticated"
    message = "Sign in to continue."


class DependencyUnavailableError(AppError):
    code = "service_unavailable"
    message = "A required service is unavailable."
