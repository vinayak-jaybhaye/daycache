"""JournalTag repository implementation."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.journal import Day, JournalEntry
from app.db.models.tag import JournalTag
from app.db.repositories.base import BaseRepository


class JournalTagRepository(BaseRepository[JournalTag]):
    """Repository handling composite primary key operations on the JournalTag model."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, JournalTag)

    async def get_by_composite_id(
        self, journal_entry_id: UUID, tag_id: UUID
    ) -> JournalTag | None:
        """Fetch a junction row by composite primary keys.

        Args:
            journal_entry_id: The UUID of the JournalEntry.
            tag_id: The UUID of the Tag.

        Returns:
            The JournalTag model instance, or None if not found.
        """
        result = await self._session.execute(
            select(JournalTag).where(
                JournalTag.journal_entry_id == journal_entry_id,
                JournalTag.tag_id == tag_id,
            )
        )
        return result.scalar_one_or_none()

    async def delete_by_composite_id(
        self, journal_entry_id: UUID, tag_id: UUID
    ) -> None:
        """Delete a junction row idempotently.

        Args:
            journal_entry_id: The UUID of the JournalEntry.
            tag_id: The UUID of the Tag.
        """
        await self._session.execute(
            delete(JournalTag).where(
                JournalTag.journal_entry_id == journal_entry_id,
                JournalTag.tag_id == tag_id,
            )
        )
        await self._session.flush()

    async def verify_entry_belongs_to_user(
        self, journal_entry_id: UUID, user_id: UUID
    ) -> bool:
        """Verify that a journal entry exists and belongs to the given user.

        Requires joining through the Day aggregate to check user ownership.

        Args:
            journal_entry_id: The UUID of the journal entry.
            user_id: The UUID of the user.

        Returns:
            True if the entry exists and belongs to the user, False otherwise.
        """
        stmt = (
            select(JournalEntry.id)
            .join(Day, JournalEntry.day_id == Day.id)
            .where(JournalEntry.id == journal_entry_id, Day.user_id == user_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None
