"""Journal repositories (Days and Journal Entries) implementation."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.db.models.journal import Day, JournalEntry
from app.db.models.mood import EntryMood
from app.db.repositories.base import BaseRepository

if TYPE_CHECKING:
    from datetime import date


class DayRepository(BaseRepository[Day]):
    """Repository handling database operations for the Day aggregate model."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Day)

    async def get_by_date(self, user_id: UUID, target_date: date) -> Day | None:
        """Fetch a Day record by user and specific calendar date.

        Args:
            user_id: The UUID of the user.
            target_date: The calendar date object.

        Returns:
            The Day aggregate instance, or None if not found.
        """
        stmt = select(Day).where(Day.user_id == user_id, Day.date == target_date)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_days_in_range(
        self, user_id: UUID, start_date: date, end_date: date
    ) -> Sequence[Day]:
        """Fetch all Day aggregates for a user within a calendar date range.

        Args:
            user_id: The UUID of the user.
            start_date: The start date.
            end_date: The end date.

        Returns:
            A sequence of Day instances sorted by date ascending.
        """
        stmt = (
            select(Day)
            .where(Day.user_id == user_id, Day.date >= start_date, Day.date <= end_date)
            .order_by(Day.date.asc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()


class JournalRepository(BaseRepository[JournalEntry]):
    """Repository handling database operations for the JournalEntry model."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, JournalEntry)

    async def get_paginated_entries(
        self,
        user_id: UUID,
        limit: int,
        cursor_data: tuple[date, datetime, UUID] | None = None,
        collection_id: UUID | None = None,
        tag_id: UUID | None = None,
        target_date: date | None = None,
        is_favorite: bool | None = None,
    ) -> tuple[Sequence[JournalEntry], int]:
        """Query and filter journal entries using keyset (cursor-based) pagination.

        Uses selectinload on tags to prevent N+1 queries when loading tags list.

        Args:
            user_id: The UUID of the user.
            limit: Maximum items to return.
            cursor_data: Optional tuple of (date, created_at, id) to start after.
            collection_id: Optional filter by collection mapping.
            tag_id: Optional filter by tag mapping.
            target_date: Optional filter by specific calendar date.
            is_favorite: Optional filter by favorite status.

        Returns:
            A tuple of (entries, total_count).
        """
        # Base queries - join to Day since users own Day and Day links entries
        count_stmt = select(func.count(JournalEntry.id)).join(
            Day, JournalEntry.day_id == Day.id
        )
        stmt = (
            select(JournalEntry)
            .join(Day, JournalEntry.day_id == Day.id)
            .options(
                selectinload(JournalEntry.tags),
                selectinload(JournalEntry.moods).joinedload(EntryMood.mood),
                joinedload(JournalEntry.day),
            )
        )

        # Standard filters
        filters = [Day.user_id == user_id, JournalEntry.deleted_at.is_(None)]

        if target_date is not None:
            filters.append(Day.date == target_date)
        if is_favorite is not None:
            filters.append(JournalEntry.is_favorite == is_favorite)

        # Conditional tag mapping filter
        if tag_id is not None:
            from app.db.models.tag import JournalTag

            count_stmt = count_stmt.join(
                JournalTag, JournalEntry.id == JournalTag.journal_entry_id
            )
            stmt = stmt.join(JournalTag, JournalEntry.id == JournalTag.journal_entry_id)
            filters.append(JournalTag.tag_id == tag_id)

        # Conditional collection mapping filter
        if collection_id is not None:
            from app.db.models.collection import CollectionEntry

            count_stmt = count_stmt.join(
                CollectionEntry, JournalEntry.id == CollectionEntry.journal_entry_id
            )
            stmt = stmt.join(
                CollectionEntry, JournalEntry.id == CollectionEntry.journal_entry_id
            )
            filters.append(CollectionEntry.collection_id == collection_id)

        # Apply where clauses for global count (excludes pagination cursors)
        count_stmt = count_stmt.where(*filters)

        # Add cursor keyset filtering if provided
        if cursor_data is not None:
            from sqlalchemy import tuple_

            c_date, c_created_at, c_uuid = cursor_data
            filters.append(
                tuple_(Day.date, JournalEntry.created_at, JournalEntry.id)
                < (c_date, c_created_at, c_uuid)
            )

        # Apply where clauses to primary select query
        stmt = stmt.where(*filters)

        # Fetch total count matching overall filters
        total = await self._session.scalar(count_stmt) or 0

        # Sort strictly by Day date desc, created_at desc, and ID desc to prevent paging collisions
        stmt = stmt.order_by(
            Day.date.desc(),
            JournalEntry.created_at.desc(),
            JournalEntry.id.desc(),
        ).limit(limit + 1)
        result = await self._session.execute(stmt)
        items = result.scalars().all()

        return items, total

    async def get_entry_by_id(
        self, entry_id: UUID, user_id: UUID
    ) -> JournalEntry | None:
        """Fetch a single journal entry by ID with tags and moods eager-loaded.

        Args:
            entry_id: The UUID of the JournalEntry.
            user_id: The UUID of the owning user.

        Returns:
            The entry instance with relationships populated, or None if not found.
        """
        stmt = (
            select(JournalEntry)
            .join(Day, JournalEntry.day_id == Day.id)
            .options(
                joinedload(JournalEntry.day),
                selectinload(JournalEntry.tags),
                selectinload(JournalEntry.moods).joinedload(EntryMood.mood),
            )
            .where(
                JournalEntry.id == entry_id,
                Day.user_id == user_id,
                JournalEntry.deleted_at.is_(None),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_entry_for_ai(self, entry_id: UUID) -> JournalEntry | None:
        """Fetch a single journal entry by ID with its Day relationship loaded.

        Args:
            entry_id: The UUID of the JournalEntry.

        Returns:
            The entry instance, or None if not found.
        """
        stmt = (
            select(JournalEntry)
            .options(
                joinedload(JournalEntry.day),
                selectinload(JournalEntry.tags),
                selectinload(JournalEntry.moods).joinedload(EntryMood.mood),
            )
            .where(
                JournalEntry.id == entry_id,
                JournalEntry.deleted_at.is_(None),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
