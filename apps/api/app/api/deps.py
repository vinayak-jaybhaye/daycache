"""Shared FastAPI dependencies.

Import these in route handlers via ``Depends()``.

Rules:
- Dependencies here are HTTP-layer concerns only.
- No business logic in dependencies.
- Business logic lives in ``modules/``.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.config import get_settings as _get_settings
from app.core.security import hash_session_token
from app.db.models import Session, User
from app.db.repositories.session import SessionRepository
from app.db.session import get_db as _get_db
from app.exceptions import UnauthorizedError


# Re-export so route handlers only need to import from ``api.deps``.
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session for the current request."""
    async for session in _get_db():
        yield session


def get_settings(
    settings: Settings = Depends(_get_settings),
) -> Settings:
    """Return the application settings singleton."""
    return settings


# ---------------------------------------------------------------------------
# Auth dependencies
# ---------------------------------------------------------------------------


async def get_current_session(
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Session:
    """Resolve the active Session based on the session cookie.

    Updates ``last_used_at`` on the session and ``last_seen_at`` on the device
    only if the record has not been updated within the last 5 minutes.

    Args:
        request: The active FastAPI HTTP request.
        db: Active database session.
        settings: Application settings.

    Returns:
        The active Session model instance with preloaded relationships.

    Raises:
        UnauthorizedError: If the token is missing, invalid, or expired.
    """
    session_token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not session_token:
        raise UnauthorizedError("Authentication credentials are required.")

    session_repo = SessionRepository(db)
    token_hash = hash_session_token(session_token)

    session = await session_repo.get_by_token_hash(token_hash)
    if session is None:
        raise UnauthorizedError("Session is invalid or has been revoked.")

    now = datetime.now(UTC)
    if session.expires_at < now:
        # Revoke expired session automatically
        await session_repo.delete(session)
        raise UnauthorizedError("Session has expired. Please log in again.")

    # Update access tracking at most once every 5 minutes (300 seconds) to avoid write traffic
    if not session.last_used_at or (now - session.last_used_at).total_seconds() > 300:
        session.last_used_at = now
        session.device.last_seen_at = now
        await db.flush()

    return session


async def get_current_user(
    session: Session = Depends(get_current_session),
) -> User:
    """Return the authenticated User for the current request.

    Args:
        session: Active session resolved from cookies.

    Returns:
        The authenticated User instance.
    """
    return session.device.user


# ---------------------------------------------------------------------------
# Background task dependencies
# ---------------------------------------------------------------------------


async def get_arq_pool() -> object:
    """Return a shared ARQ Redis pool for enqueueing background jobs.

    Creates a new pool connection per request.  In production this should
    be promoted to a lifespan-managed singleton to avoid connection overhead.
    """
    from arq import create_pool
    from arq.connections import RedisSettings

    settings = _get_settings()
    return await create_pool(RedisSettings.from_dsn(str(settings.REDIS_URL)))
