"""EntryMoodRepository — manage the entry ↔ mood junction table."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.db.models.journal import Day, JournalEntry
from app.db.models.mood import EntryMood
from app.db.repositories.base import BaseRepository


class EntryMoodRepository(BaseRepository[EntryMood]):
    """Repository for composite-key operations on the EntryMood junction model."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, EntryMood)

    async def get_by_composite_id(
        self, journal_entry_id: UUID, mood_id: UUID
    ) -> EntryMood | None:
        """Fetch a junction row by composite keys.

        Args:
            journal_entry_id: The UUID of the JournalEntry.
            mood_id: The UUID of the Mood.

        Returns:
            The EntryMood instance, or None if not found.
        """
        result = await self._session.execute(
            select(EntryMood)
            .options(joinedload(EntryMood.mood))
            .where(
                EntryMood.journal_entry_id == journal_entry_id,
                EntryMood.mood_id == mood_id,
            )
        )
        return result.scalar_one_or_none()

    async def delete_by_composite_id(
        self, journal_entry_id: UUID, mood_id: UUID
    ) -> None:
        """Delete a junction row idempotently.

        Args:
            journal_entry_id: The UUID of the JournalEntry.
            mood_id: The UUID of the Mood.
        """
        await self._session.execute(
            delete(EntryMood).where(
                EntryMood.journal_entry_id == journal_entry_id,
                EntryMood.mood_id == mood_id,
            )
        )
        await self._session.flush()

    async def verify_entry_belongs_to_user(
        self, journal_entry_id: UUID, user_id: UUID
    ) -> bool:
        """Verify that a journal entry exists and belongs to the given user.

        Args:
            journal_entry_id: The UUID of the journal entry.
            user_id: The UUID of the user.

        Returns:
            True if the entry exists and belongs to the user, False otherwise.
        """
        stmt = (
            select(JournalEntry.id)
            .join(Day, JournalEntry.day_id == Day.id)
            .where(
                JournalEntry.id == journal_entry_id,
                Day.user_id == user_id,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None
