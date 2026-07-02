"""Shared FastAPI dependencies.

Import these in route handlers via ``Depends()``.

Rules:
- Dependencies here are HTTP-layer concerns only.
- No business logic in dependencies.
- Business logic lives in ``modules/``.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.config import get_settings as _get_settings
from app.db.session import get_db as _get_db


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
# Auth stubs — implemented when modules/auth is ready
# ---------------------------------------------------------------------------


async def get_current_user() -> None:  # type: ignore[return]
    """Return the authenticated user for the current request.

    Not yet implemented — will be wired to modules/auth once
    session-based authentication is built.

    Raises:
        NotImplementedError: Always, until auth is implemented.
    """
    raise NotImplementedError(
        "get_current_user() is not yet implemented. "
        "Implement modules/auth/service.py first."
    )


async def require_auth() -> None:  # type: ignore[return]
    """Enforce that the current request is authenticated.

    Not yet implemented.
    """
    raise NotImplementedError(
        "require_auth() is not yet implemented. "
        "Implement modules/auth/service.py first."
    )
