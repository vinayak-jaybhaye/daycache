"""Device repository implementation."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Device
from app.db.repositories.base import BaseRepository


class DeviceRepository(BaseRepository[Device]):
    """Repository handling persistence operations for the Device model."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Device)

    async def get_by_installation_id(
        self, user_id: UUID, installation_id: str
    ) -> Device | None:
        """Fetch a registered device by user ID and installation ID.

        Args:
            user_id: The UUID of the owner user.
            installation_id: Stable app-generated client installation identifier.

        Returns:
            The Device model instance, or None if not found.
        """
        result = await self._session.execute(
            select(Device).where(
                Device.user_id == user_id,
                Device.installation_id == installation_id,
            )
        )
        return result.scalar_one_or_none()
