"""UserSettings repository implementation."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UserSettings
from app.db.repositories.base import BaseRepository


class SettingsRepository(BaseRepository[UserSettings]):
    """Repository handling persistence operations for the UserSettings model."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, UserSettings)

    async def get_by_user_id(self, user_id: UUID) -> UserSettings | None:
        """Fetch the settings record for a given user.

        Args:
            user_id: The UUID of the owning user.

        Returns:
            The UserSettings instance, or None if not found.
        """
        result = await self._session.execute(
            select(UserSettings).where(UserSettings.user_id == str(user_id))
        )
        return result.scalar_one_or_none()

    async def update(self, settings: UserSettings) -> UserSettings:
        """Persist in-place mutations to a UserSettings instance.

        The caller is responsible for modifying the fields before calling
        this method.  Only a flush + refresh is required — no add() needed
        because the instance is already tracked by the session.

        Args:
            settings: The mutated UserSettings instance attached to the session.

        Returns:
            The refreshed UserSettings instance.
        """
        await self._session.flush()
        await self._session.refresh(settings)
        return settings
