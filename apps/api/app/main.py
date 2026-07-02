"""DayCache API entry point.

This module wires together all application components:
- Application lifespan (startup / shutdown)
- Middleware (CORS, request logging)
- Exception handlers
- API router

No business logic lives here. Keep this file thin.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import router
from app.core.config import get_settings
from app.core.lifespan import lifespan
from app.exceptions.handlers import register_exception_handlers
from app.middleware.logging import RequestLoggingMiddleware

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    # Disable interactive docs in production.
    docs_url=None if settings.APP_ENV == "production" else "/docs",
    redoc_url=None if settings.APP_ENV == "production" else "/redoc",
    openapi_url=None if settings.APP_ENV == "production" else "/openapi.json",
)

# ---------------------------------------------------------------------------
# Middleware (registered in reverse order — last added runs first)
# ---------------------------------------------------------------------------

# 1. CORS — outermost so preflight requests are handled before any other logic.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(origin) for origin in settings.CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Request logging — assigns X-Request-ID and logs every request.
app.add_middleware(RequestLoggingMiddleware)

# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------

register_exception_handlers(app)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(router)

# ---------------------------------------------------------------------------
# Local storage internal endpoints (development only)
# ---------------------------------------------------------------------------
# When STORAGE_BACKEND=local, mount signed upload/download endpoints so the
# client can PUT directly without the API proxying bytes — mirrors the
# presigned URL pattern used in production with S3.
if settings.STORAGE_BACKEND == "local":
    from app.storage.local import LocalStorageBackend

    _local_storage = LocalStorageBackend()
    app.include_router(_local_storage.make_internal_router(), prefix="/internal")
