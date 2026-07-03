"""Tag service layer."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from app.db.models.organization import Tag
from app.db.repositories.tag import TagRepository
from app.exceptions import ConflictError, NotFoundError
from app.modules.tags.schemas import TagResponse

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.tags.schemas import TagCreate, TagUpdate


class TagService:
    """Orchestrates operations for managing user-defined tags."""

    @staticmethod
    async def create_tag(
        db: AsyncSession, user_id: UUID, data: TagCreate
    ) -> TagResponse:
        """Create a new tag for the user.

        Args:
            db: Database session.
            user_id: The UUID of the user.
            data: Schema containing tag name and color.

        Returns:
            The created TagResponse schema.

        Raises:
            ConflictError: If a tag with the same name already exists for this user.
        """
        tag_repo = TagRepository(db)

        # Check for duplicate tag names for this user
        existing_tag = await tag_repo.get_by_name(user_id, data.name)
        if existing_tag is not None:
            raise ConflictError(f"Tag with name '{data.name}' already exists.")

        tag = Tag(
            user_id=user_id,
            name=data.name,
            color=data.color,
        )
        tag = await tag_repo.create(tag)

        return TagResponse(
            id=tag.id,
            name=tag.name,
            color=tag.color,
            entry_count=0,
            created_at=tag.created_at,
        )

    @staticmethod
    async def get_tag(db: AsyncSession, user_id: UUID, tag_id: UUID) -> TagResponse:
        """Fetch a specific tag for a user.

        Args:
            db: Database session.
            user_id: The UUID of the user.
            tag_id: The UUID of the tag.

        Returns:
            The TagResponse schema.

        Raises:
            NotFoundError: If the tag is not found or does not belong to the user.
        """
        tag_repo = TagRepository(db)
        result = await tag_repo.get_tag_with_count(user_id, tag_id)
        if result is None:
            raise NotFoundError("Tag not found.")

        tag, entry_count = result
        return TagResponse(
            id=tag.id,
            name=tag.name,
            color=tag.color,
            entry_count=entry_count,
            created_at=tag.created_at,
        )

    @staticmethod
    async def list_tags(db: AsyncSession, user_id: UUID) -> list[TagResponse]:
        """List all tags belonging to a user with their associated entry counts.

        Args:
            db: Database session.
            user_id: The UUID of the user.

        Returns:
            A list of TagResponse schemas.
        """
        tag_repo = TagRepository(db)
        results = await tag_repo.get_user_tags_with_counts(user_id)

        return [
            TagResponse(
                id=tag.id,
                name=tag.name,
                color=tag.color,
                entry_count=count,
                created_at=tag.created_at,
            )
            for tag, count in results
        ]

    @staticmethod
    async def update_tag(
        db: AsyncSession, user_id: UUID, tag_id: UUID, data: TagUpdate
    ) -> TagResponse:
        """Update properties of an existing tag.

        Args:
            db: Database session.
            user_id: The UUID of the user.
            tag_id: The UUID of the tag.
            data: Schema containing fields to update.

        Returns:
            The updated TagResponse schema.

        Raises:
            NotFoundError: If the tag is not found or does not belong to the user.
            ConflictError: If the name is changed to an already existing tag name.
        """
        tag_repo = TagRepository(db)
        result = await tag_repo.get_tag_with_count(user_id, tag_id)
        if result is None:
            raise NotFoundError("Tag not found.")

        tag, entry_count = result

        if data.name is not None and data.name != tag.name:
            # Check name conflict
            existing_tag = await tag_repo.get_by_name(user_id, data.name)
            if existing_tag is not None:
                raise ConflictError(f"Tag with name '{data.name}' already exists.")
            tag.name = data.name

        if data.color is not None:
            tag.color = data.color

        await db.flush()
        await db.refresh(tag)

        return TagResponse(
            id=tag.id,
            name=tag.name,
            color=tag.color,
            entry_count=entry_count,
            created_at=tag.created_at,
        )

    @staticmethod
    async def delete_tag(db: AsyncSession, user_id: UUID, tag_id: UUID) -> None:
        """Delete a user's tag.

        Args:
            db: Database session.
            user_id: The UUID of the user.
            tag_id: The UUID of the tag.

        Raises:
            NotFoundError: If the tag is not found or does not belong to the user.
        """
        tag_repo = TagRepository(db)
        tag = await tag_repo.get_by_id(tag_id)
        if tag is None or tag.user_id != user_id:
            raise NotFoundError("Tag not found.")

        await tag_repo.delete(tag)
