"""Async SQLAlchemy engine lifecycle.

``create_engine()`` is called once during application startup (lifespan).
``dispose_engine()`` is called during shutdown.

Do not import this module outside of ``core/lifespan.py`` and ``db/session.py``.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Module-level reference populated by create_engine() / cleared by dispose_engine().
_engine: AsyncEngine | None = None


def create_engine() -> AsyncEngine:
    """Create and cache the application's async database engine.

    Called during application startup. Subsequent calls return the same engine.

    Returns:
        The configured ``AsyncEngine`` instance.
    """
    global _engine
    if _engine is not None:
        return _engine

    settings = get_settings()
    _engine = create_async_engine(
        str(settings.DATABASE_URL),
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        echo=False,
    )
    logger.info("Database engine created", extra={"env": settings.APP_ENV})
    return _engine


def get_engine() -> AsyncEngine:
    """Return the active engine.

    Raises:
        RuntimeError: If the engine has not been initialised yet.
    """
    if _engine is None:
        msg = "Database engine is not initialised. Call create_engine() first."
        raise RuntimeError(msg)
    return _engine


async def dispose_engine() -> None:
    """Gracefully close all pooled connections.

    Called during application shutdown.
    """
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        logger.info("Database engine disposed")
