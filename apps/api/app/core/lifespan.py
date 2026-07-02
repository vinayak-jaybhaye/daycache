"""Application lifespan context manager.

Executed once at startup and once at shutdown.
Keeps ``main.py`` clean by centralising all initialisation logic here.

Startup sequence:
1. Configure logging
2. Log application start
3. Create database engine

Shutdown sequence:
1. Dispose database engine
2. Log application stop
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.engine import create_engine, dispose_engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """FastAPI lifespan context manager."""
    settings = get_settings()

    # --- Startup ----------------------------------------------------------
    configure_logging(
        log_level=settings.LOG_LEVEL,
        json_logs=settings.APP_ENV != "development",
    )

    logger = get_logger(__name__)
    logger.info(
        "Starting %s v%s [%s]",
        settings.APP_NAME,
        settings.APP_VERSION,
        settings.APP_ENV,
    )

    create_engine()

    # --- Application runs -------------------------------------------------
    yield

    # --- Shutdown ---------------------------------------------------------
    logger.info("Shutting down %s", settings.APP_NAME)
    await dispose_engine()
