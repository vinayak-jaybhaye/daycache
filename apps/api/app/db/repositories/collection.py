"""Collection repository implementation."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.organization import Collection, CollectionEntry
from app.db.repositories.base import BaseRepository

if TYPE_CHECKING:
    from app.db.models import Collection


class CollectionRepository(BaseRepository[Collection]):
    """Repository handling database operations for the Collection model."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Collection)

    async def get_by_name(self, user_id: UUID, name: str) -> Collection | None:
        """Fetch a collection by name for a specific user.

        Args:
            user_id: The UUID of the user.
            name: The lowercase collection name.

        Returns:
            The Collection instance, or None if not found.
        """
        result = await self._session.execute(
            select(Collection).where(
                Collection.user_id == user_id, Collection.name == name
            )
        )
        return result.scalar_one_or_none()

    async def get_user_collections_with_counts(
        self, user_id: UUID
    ) -> Sequence[tuple[Collection, int]]:
        """Retrieve all collections for a user with their associated entry counts.

        Uses a single LEFT OUTER JOIN and GROUP BY query to avoid N+1 issues.

        Args:
            user_id: The UUID of the user.

        Returns:
            A sequence of tuples containing (Collection, entry_count),
            ordered by is_pinned DESC and then alphabetically by name.
        """
        stmt = (
            select(
                Collection,
                func.count(CollectionEntry.journal_entry_id).label("entry_count"),
            )
            .outerjoin(CollectionEntry, Collection.id == CollectionEntry.collection_id)
            .where(Collection.user_id == user_id)
            .group_by(Collection.id)
            .order_by(Collection.is_pinned.desc(), Collection.name)
        )
        result = await self._session.execute(stmt)
        return result.all()  # type: ignore[return-value]

    async def get_collection_with_count(
        self, user_id: UUID, collection_id: UUID
    ) -> tuple[Collection, int] | None:
        """Retrieve a collection by ID for a specific user with its entry count.

        Args:
            user_id: The UUID of the user.
            collection_id: The UUID of the collection.

        Returns:
            A tuple of (Collection, entry_count), or None if not found.
        """
        stmt = (
            select(
                Collection,
                func.count(CollectionEntry.journal_entry_id).label("entry_count"),
            )
            .outerjoin(CollectionEntry, Collection.id == CollectionEntry.collection_id)
            .where(Collection.user_id == user_id, Collection.id == collection_id)
            .group_by(Collection.id)
        )
        result = await self._session.execute(stmt)
        return result.one_or_none()  # type: ignore[return-value]
