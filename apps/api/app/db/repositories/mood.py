"""MoodRepository — read-only access to the predefined mood catalog."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.mood import Mood
from app.db.repositories.base import BaseRepository


class MoodRepository(BaseRepository[Mood]):
    """Repository providing read access to the system mood catalog."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Mood)

    async def list_all(self) -> list[Mood]:
        """Return all predefined moods ordered by name."""
        result = await self._session.execute(select(Mood).order_by(Mood.name))
        return list(result.scalars().all())
