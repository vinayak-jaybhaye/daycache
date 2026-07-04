"""Global FastAPI exception handlers.

Registered on the FastAPI app in ``main.py`` via ``register_exception_handlers()``.

Every error response follows the same envelope::

    {
        "error": "NOT_FOUND",
        "detail": "Entry not found.",
        "request_id": "a1b2c3d4-..."
    }

The ``request_id`` is sourced from the middleware's ``ContextVar`` so that
every error response carries the same ID as the corresponding access log entry.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm.exc import StaleDataError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.exceptions.base import AppException, ConflictError
from app.middleware.logging import get_request_id

logger = logging.getLogger(__name__)


def _error_body(code: str, detail: str, request_id: str) -> dict[str, str]:
    return {"error": code, "detail": detail, "request_id": request_id}


async def _app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    request_id = get_request_id()
    logger.warning(
        "Application exception: %s — %s",
        exc.code,
        exc.detail,
        extra={"request_id": request_id},
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(exc.code, exc.detail, request_id),
    )


async def _stale_data_exception_handler(
    request: Request, exc: StaleDataError
) -> JSONResponse:
    request_id = get_request_id()
    logger.warning(
        "Optimistic locking conflict: StaleDataError raised.",
        extra={"request_id": request_id},
    )
    conflict_exc = ConflictError("The entry has been updated by another client.")
    return await _app_exception_handler(request, conflict_exc)


async def _http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    request_id = get_request_id()
    detail = str(exc.detail) if exc.detail else "HTTP error"
    logger.warning(
        "HTTP exception: %s — %s",
        exc.status_code,
        detail,
        extra={"request_id": request_id},
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body("HTTP_ERROR", detail, request_id),
        headers=getattr(exc, "headers", None),
    )


async def _validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    request_id = get_request_id()
    errors = [
        {"field": " → ".join(str(loc) for loc in err["loc"]), "msg": err["msg"]}
        for err in exc.errors()
    ]
    logger.info(
        "Validation error on %s %s",
        request.method,
        request.url.path,
        extra={"request_id": request_id, "errors": errors},
    )
    return JSONResponse(
        status_code=422,
        content={
            "error": "VALIDATION_ERROR",
            "detail": "Request validation failed.",
            "errors": errors,
            "request_id": request_id,
        },
    )


async def _unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    request_id = get_request_id()
    logger.exception(
        "Unhandled exception on %s %s",
        request.method,
        request.url.path,
        extra={"request_id": request_id},
    )
    return JSONResponse(
        status_code=500,
        content=_error_body(
            "INTERNAL_ERROR",
            "An unexpected error occurred. Please try again later.",
            request_id,
        ),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all global exception handlers to the FastAPI application."""
    app.add_exception_handler(AppException, _app_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StaleDataError, _stale_data_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _unhandled_exception_handler)
