"""Request logging middleware.

Responsibilities:
- Accept or generate a ``X-Request-ID`` per request.
- Store it in a ``ContextVar`` accessible to exception handlers.
- Attach it to the response headers.
- Emit a structured access-log entry after the response is sent.

Log fields per request:
    request_id, method, path, status, duration_ms,
    client_ip, user_agent
"""

from __future__ import annotations

import logging
import time
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# ContextVar makes the request ID available to any coroutine in the
# current request's task, including exception handlers.
_request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    """Return the request ID for the current request context.

    Returns an empty string if called outside a request context.
    """
    return _request_id_ctx.get()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that logs every HTTP request with correlation ID."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # --- Request ID ---------------------------------------------------
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = _request_id_ctx.set(request_id)

        # --- Timing -------------------------------------------------------
        start = time.perf_counter()

        try:
            response: Response = await call_next(request)
        except Exception:
            raise
        finally:
            _request_id_ctx.reset(token)

        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        # --- Client metadata ---------------------------------------------
        forwarded_for = request.headers.get("X-Forwarded-For")
        client_ip = (
            forwarded_for.split(",")[0].strip()
            if forwarded_for
            else (request.client.host if request.client else "unknown")
        )
        user_agent = request.headers.get("User-Agent")

        # --- Attach correlation header to response -----------------------
        response.headers["X-Request-ID"] = request_id

        # --- Log level by status -----------------------------------------
        status = response.status_code
        if status >= 500:
            log = logger.error
        elif status >= 400:
            log = logger.warning
        else:
            log = logger.info

        extra: dict[str, object] = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status": status,
            "duration_ms": duration_ms,
            "client_ip": client_ip,
        }
        if user_agent:
            extra["user_agent"] = user_agent

        log(
            "%s %s %s (%.2fms)",
            request.method,
            request.url.path,
            status,
            duration_ms,
            extra=extra,
        )

        return response
