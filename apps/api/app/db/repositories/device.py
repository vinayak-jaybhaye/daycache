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

    async def get_by_identifier(
        self, user_id: UUID, device_identifier: str
    ) -> Device | None:
        """Fetch a registered device by user ID and device identifier.

        Args:
            user_id: The UUID of the owner user.
            device_identifier: Stable app-generated client identifier.

        Returns:
            The Device model instance, or None if not found.
        """
        result = await self._session.execute(
            select(Device).where(
                Device.user_id == user_id,
                Device.device_identifier == device_identifier,
            )
        )
        return result.scalar_one_or_none()
