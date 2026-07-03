"""Shared pytest fixtures for the DayCache API test suite.

Provides:
- ``async_client``: an ``httpx.AsyncClient`` wired to the FastAPI test app.
- ``db_session``: an ``AsyncSession`` that rolls back after every test.
- Environment override for ``APP_ENV=test``.

Usage::

    async def test_health(async_client: AsyncClient) -> None:
        response = await async_client.get("/api/v1/health")
        assert response.status_code == 200
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Force development environment for tests (APP_ENV must be a valid literal).
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://daycache:daycache@localhost:5432/daycache_test",
)
os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-long-enough-32chars!")
os.environ.setdefault("AI_EMBEDDING_PROVIDER", "mock")
os.environ.setdefault("AI_EMBEDDING_MODEL", "mock-model")

from app.api.deps import get_db
from app.main import app

# ---------------------------------------------------------------------------
# Async HTTP client
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Yield an async HTTP client pointed at the test app."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


# ---------------------------------------------------------------------------
# Database session with automatic rollback
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an AsyncSession that rolls back after every test.

    This keeps tests isolated without truncating tables between runs.
    Override ``get_db`` on the FastAPI app so route handlers share
    the same transactional session as the test.
    """
    database_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(database_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        async with session.begin():
            # Inject the test session into FastAPI's dependency system.
            async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
                yield session

            app.dependency_overrides[get_db] = override_get_db
            yield session
            # Rollback is triggered automatically when the block exits.
            await session.rollback()

        app.dependency_overrides.clear()

    await engine.dispose()
