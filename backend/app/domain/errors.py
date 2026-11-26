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


class DependencyUnavailableError(AppError):
    code = "service_unavailable"
    message = "A required service is unavailable."
