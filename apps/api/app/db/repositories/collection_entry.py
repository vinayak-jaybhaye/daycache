"""CollectionEntry repository implementation."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.journal import Day, JournalEntry
from app.db.models.organization import CollectionEntry
from app.db.repositories.base import BaseRepository


class CollectionEntryRepository(BaseRepository[CollectionEntry]):
    """Repository handling composite primary key operations on the CollectionEntry model."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CollectionEntry)

    async def get_by_composite_id(
        self, collection_id: UUID, journal_entry_id: UUID
    ) -> CollectionEntry | None:
        """Fetch a junction row by composite primary keys.

        Args:
            collection_id: The UUID of the Collection.
            journal_entry_id: The UUID of the JournalEntry.

        Returns:
            The CollectionEntry model instance, or None if not found.
        """
        result = await self._session.execute(
            select(CollectionEntry).where(
                CollectionEntry.collection_id == collection_id,
                CollectionEntry.journal_entry_id == journal_entry_id,
            )
        )
        return result.scalar_one_or_none()

    async def delete_by_composite_id(
        self, collection_id: UUID, journal_entry_id: UUID
    ) -> None:
        """Delete a junction row idempotently.

        Args:
            collection_id: The UUID of the Collection.
            journal_entry_id: The UUID of the JournalEntry.
        """
        await self._session.execute(
            delete(CollectionEntry).where(
                CollectionEntry.collection_id == collection_id,
                CollectionEntry.journal_entry_id == journal_entry_id,
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
