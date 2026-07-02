"""Application exception hierarchy.

Raise these exceptions from modules and repositories.
The global handlers in ``exceptions/handlers.py`` convert them to
consistent HTTP error responses.

Usage::

    from app.exceptions import NotFoundError
    raise NotFoundError("Entry not found")
"""

from __future__ import annotations


class AppException(Exception):
    """Base class for all application exceptions.

    Attributes:
        status_code: The HTTP status code to return to the client.
        detail:      Human-readable error message.
        code:        Machine-readable error code for the client.
    """

    status_code: int = 500
    code: str = "INTERNAL_ERROR"

    def __init__(self, detail: str | None = None) -> None:
        self.detail = (
            detail or self.__class__.__doc__ or "An unexpected error occurred."
        )
        super().__init__(self.detail)


class NotFoundError(AppException):
    """Resource not found."""

    status_code = 404
    code = "NOT_FOUND"


class ConflictError(AppException):
    """Resource already exists or state conflict."""

    status_code = 409
    code = "CONFLICT"


class UnauthorizedError(AppException):
    """Authentication required."""

    status_code = 401
    code = "UNAUTHORIZED"


class ForbiddenError(AppException):
    """Insufficient permissions."""

    status_code = 403
    code = "FORBIDDEN"


class UnprocessableError(AppException):
    """Business rule validation failed."""

    status_code = 422
    code = "UNPROCESSABLE"
