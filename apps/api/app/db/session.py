"""Async session factory and FastAPI dependency."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

# Session factory — created lazily on first use via get_db().
# expire_on_commit=False keeps ORM objects usable after commit without
# issuing additional SELECT queries.
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        # Auto-initialise the engine if not already done (e.g. in tests
        # that bypass the lifespan).
        from app.db.engine import create_engine

        engine = create_engine()
        _session_factory = async_sessionmaker(
            bind=engine,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session per request.

    Commits on clean exit; rolls back on any exception.

    Usage::

        @router.get("/items")
        async def list_items(db: AsyncSession = Depends(get_db)) -> ...:
            ...
    """
    factory = _get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
