"""Collection service layer."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from app.db.models.collection import Collection, CollectionEntry
from app.db.repositories.collection import CollectionRepository
from app.db.repositories.collection_entry import CollectionEntryRepository
from app.exceptions import ConflictError, NotFoundError
from app.modules.collections.schemas import CollectionResponse

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.collections.schemas import CollectionCreate, CollectionUpdate


class CollectionService:
    """Orchestrates operations for managing user collections and entries."""

    @staticmethod
    async def create_collection(
        db: AsyncSession, user_id: UUID, data: CollectionCreate
    ) -> CollectionResponse:
        """Create a new collection for the user.

        Args:
            db: Database session.
            user_id: The UUID of the user.
            data: Schema containing collection data.

        Returns:
            The created CollectionResponse schema.

        Raises:
            ConflictError: If a collection with the same name already exists for this user.
        """
        collection_repo = CollectionRepository(db)

        # Check for duplicate names for this user
        existing_col = await collection_repo.get_by_name(user_id, data.name)
        if existing_col is not None:
            raise ConflictError(f"Collection with name '{data.name}' already exists.")

        collection = Collection(
            user_id=user_id,
            name=data.name,
            description=data.description,
            icon=data.icon,
            is_pinned=data.is_pinned,
        )
        collection = await collection_repo.create(collection)

        return CollectionResponse(
            id=collection.id,
            name=collection.name,
            description=collection.description,
            icon=collection.icon,
            is_pinned=collection.is_pinned,
            entry_count=0,
            created_at=collection.created_at,
            updated_at=collection.updated_at,
        )

    @staticmethod
    async def get_collection(
        db: AsyncSession, user_id: UUID, collection_id: UUID
    ) -> CollectionResponse:
        """Fetch a specific collection for a user.

        Args:
            db: Database session.
            user_id: The UUID of the user.
            collection_id: The UUID of the collection.

        Returns:
            The CollectionResponse schema.

        Raises:
            NotFoundError: If the collection is not found or does not belong to the user.
        """
        collection_repo = CollectionRepository(db)
        result = await collection_repo.get_collection_with_count(user_id, collection_id)
        if result is None:
            raise NotFoundError("Collection not found.")

        collection, entry_count = result
        return CollectionResponse(
            id=collection.id,
            name=collection.name,
            description=collection.description,
            icon=collection.icon,
            is_pinned=collection.is_pinned,
            entry_count=entry_count,
            created_at=collection.created_at,
            updated_at=collection.updated_at,
        )

    @staticmethod
    async def list_collections(
        db: AsyncSession, user_id: UUID
    ) -> list[CollectionResponse]:
        """List all collections belonging to a user with their associated entry counts.

        Args:
            db: Database session.
            user_id: The UUID of the user.

        Returns:
            A list of CollectionResponse schemas.
        """
        collection_repo = CollectionRepository(db)
        results = await collection_repo.get_user_collections_with_counts(user_id)

        return [
            CollectionResponse(
                id=col.id,
                name=col.name,
                description=col.description,
                icon=col.icon,
                is_pinned=col.is_pinned,
                entry_count=count,
                created_at=col.created_at,
                updated_at=col.updated_at,
            )
            for col, count in results
        ]

    @staticmethod
    async def update_collection(
        db: AsyncSession, user_id: UUID, collection_id: UUID, data: CollectionUpdate
    ) -> CollectionResponse:
        """Update metadata of an existing collection.

        Args:
            db: Database session.
            user_id: The UUID of the user.
            collection_id: The UUID of the collection.
            data: Schema containing fields to update.

        Returns:
            The updated CollectionResponse schema.

        Raises:
            NotFoundError: If the collection is not found or does not belong to the user.
            ConflictError: If the name is changed to an already existing collection name.
        """
        collection_repo = CollectionRepository(db)
        result = await collection_repo.get_collection_with_count(user_id, collection_id)
        if result is None:
            raise NotFoundError("Collection not found.")

        collection, entry_count = result

        if data.name is not None and data.name != collection.name:
            # Check name conflict
            existing_col = await collection_repo.get_by_name(user_id, data.name)
            if existing_col is not None:
                raise ConflictError(
                    f"Collection with name '{data.name}' already exists."
                )
            collection.name = data.name

        if data.description is not None:
            collection.description = data.description

        if data.icon is not None:
            collection.icon = data.icon

        if data.is_pinned is not None:
            collection.is_pinned = data.is_pinned

        await db.flush()
        await db.refresh(collection)

        return CollectionResponse(
            id=collection.id,
            name=collection.name,
            description=collection.description,
            icon=collection.icon,
            is_pinned=collection.is_pinned,
            entry_count=entry_count,
            created_at=collection.created_at,
            updated_at=collection.updated_at,
        )

    @staticmethod
    async def delete_collection(
        db: AsyncSession, user_id: UUID, collection_id: UUID
    ) -> None:
        """Delete a user's collection.

        Args:
            db: Database session.
            user_id: The UUID of the user.
            collection_id: The UUID of the collection.

        Raises:
            NotFoundError: If the collection is not found or does not belong to the user.
        """
        collection_repo = CollectionRepository(db)
        collection = await collection_repo.get_by_id(collection_id)
        if collection is None or collection.user_id != user_id:
            raise NotFoundError("Collection not found.")

        await collection_repo.delete(collection)

    @staticmethod
    async def add_entry_to_collection(
        db: AsyncSession, user_id: UUID, collection_id: UUID, journal_entry_id: UUID
    ) -> None:
        """Add a journal entry to a collection idempotently.

        Args:
            db: Database session.
            user_id: The UUID of the user.
            collection_id: The UUID of the collection.
            journal_entry_id: The UUID of the journal entry to add.

        Raises:
            NotFoundError: If either the collection or the journal entry is not found
                           or does not belong to the user.
        """
        collection_repo = CollectionRepository(db)
        collection = await collection_repo.get_by_id(collection_id)
        if collection is None or collection.user_id != user_id:
            raise NotFoundError("Collection not found.")

        col_entry_repo = CollectionEntryRepository(db)

        # Verify that the journal entry exists and belongs to the user
        belongs = await col_entry_repo.verify_entry_belongs_to_user(
            journal_entry_id, user_id
        )
        if not belongs:
            raise NotFoundError("Journal entry not found.")

        # Add connection idempotently
        existing = await col_entry_repo.get_by_composite_id(
            collection_id, journal_entry_id
        )
        if existing is None:
            col_entry = CollectionEntry(
                collection_id=collection_id,
                journal_entry_id=journal_entry_id,
                position=0,
            )
            await col_entry_repo.create(col_entry)

    @staticmethod
    async def remove_entry_from_collection(
        db: AsyncSession, user_id: UUID, collection_id: UUID, journal_entry_id: UUID
    ) -> None:
        """Remove a journal entry from a collection idempotently.

        Args:
            db: Database session.
            user_id: The UUID of the user.
            collection_id: The UUID of the collection.
            journal_entry_id: The UUID of the journal entry.

        Raises:
            NotFoundError: If the collection is not found or does not belong to the user.
        """
        collection_repo = CollectionRepository(db)
        collection = await collection_repo.get_by_id(collection_id)
        if collection is None or collection.user_id != user_id:
            raise NotFoundError("Collection not found.")

        col_entry_repo = CollectionEntryRepository(db)
        await col_entry_repo.delete_by_composite_id(collection_id, journal_entry_id)
