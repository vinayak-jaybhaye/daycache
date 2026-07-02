"""User repository implementation."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.db.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository handling persistence operations for the User model."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, User)

    async def get_by_email(self, email: str) -> User | None:
        """Fetch a user by email case-insensitively.

        Args:
            email: The email address to look up.

        Returns:
            The User model instance, or None if not found.
        """
        # CITEXT compares case-insensitively automatically in Postgres.
        result = await self._session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()
