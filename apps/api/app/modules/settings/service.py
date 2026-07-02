"""Settings module business service."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UserSettings
from app.db.repositories import SettingsRepository
from app.exceptions import NotFoundError

if TYPE_CHECKING:
    from app.modules.settings.schemas import UpdateSettingsRequest


class SettingsService:
    """Orchestrates retrieval and updates of user application preferences."""

    @staticmethod
    async def get_settings(db: AsyncSession, user_id: UUID) -> UserSettings:
        """Return the settings record for the authenticated user.

        Args:
            db: Active database session.
            user_id: The UUID of the authenticated user.

        Returns:
            The UserSettings instance.

        Raises:
            NotFoundError: If the settings record is missing (data integrity issue).
        """
        settings_repo = SettingsRepository(db)
        settings = await settings_repo.get_by_user_id(user_id)
        if settings is None:
            raise NotFoundError("Settings not found.")
        return settings

    @staticmethod
    async def update_settings(
        db: AsyncSession,
        user_id: UUID,
        data: UpdateSettingsRequest,
    ) -> UserSettings:
        """Apply a partial update to the user's settings.

        Only fields explicitly set in ``data`` are written to the database;
        all other fields retain their current values.

        Args:
            db: Active database session.
            user_id: The UUID of the authenticated user.
            data: Partial settings update payload.

        Returns:
            The updated UserSettings instance.

        Raises:
            NotFoundError: If the settings record is missing.
        """
        settings_repo = SettingsRepository(db)
        settings = await settings_repo.get_by_user_id(user_id)
        if settings is None:
            raise NotFoundError("Settings not found.")

        # Apply only the fields that were explicitly provided in the request
        updates = data.model_dump(exclude_unset=True)
        for field, value in updates.items():
            setattr(settings, field, value)

        return await settings_repo.update(settings)
