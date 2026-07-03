"""Tag repository implementation."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.tag import JournalTag, Tag
from app.db.repositories.base import BaseRepository

if TYPE_CHECKING:
    from app.db.models import Tag


class TagRepository(BaseRepository[Tag]):
    """Repository handling database operations for the Tag model."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Tag)

    async def get_by_name(self, user_id: UUID, name: str) -> Tag | None:
        """Fetch a tag by name for a specific user.

        Args:
            user_id: The UUID of the user.
            name: The lowercase tag name.

        Returns:
            The Tag instance, or None if not found.
        """
        result = await self._session.execute(
            select(Tag).where(Tag.user_id == user_id, Tag.name == name)
        )
        return result.scalar_one_or_none()

    async def get_user_tags_with_counts(
        self, user_id: UUID
    ) -> Sequence[tuple[Tag, int]]:
        """Retrieve all tags for a user with their associated entry counts.

        Uses a single LEFT OUTER JOIN and GROUP BY query to avoid N+1 issues.

        Args:
            user_id: The UUID of the user.

        Returns:
            A sequence of tuples containing (Tag, entry_count), ordered alphabetically.
        """
        stmt = (
            select(Tag, func.count(JournalTag.journal_entry_id).label("entry_count"))
            .outerjoin(JournalTag, Tag.id == JournalTag.tag_id)
            .where(Tag.user_id == user_id)
            .group_by(Tag.id)
            .order_by(Tag.name)
        )
        result = await self._session.execute(stmt)
        return result.all()  # type: ignore[return-value]

    async def get_tag_with_count(
        self, user_id: UUID, tag_id: UUID
    ) -> tuple[Tag, int] | None:
        """Retrieve a tag by ID for a specific user with its entry count.

        Args:
            user_id: The UUID of the user.
            tag_id: The UUID of the tag.

        Returns:
            A tuple of (Tag, entry_count), or None if not found.
        """
        stmt = (
            select(Tag, func.count(JournalTag.journal_entry_id).label("entry_count"))
            .outerjoin(JournalTag, Tag.id == JournalTag.tag_id)
            .where(Tag.user_id == user_id, Tag.id == tag_id)
            .group_by(Tag.id)
        )
        result = await self._session.execute(stmt)
        return result.one_or_none()  # type: ignore[return-value]
