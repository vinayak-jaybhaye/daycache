"""Collections API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.deps import get_current_user, get_db
from app.db.models import User
from app.modules.collections.schemas import (
    CollectionCreate,
    CollectionEntryAdd,
    CollectionResponse,
    CollectionUpdate,
)
from app.modules.collections.service import CollectionService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.post(
    "",
    response_model=CollectionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_collection(
    data: CollectionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CollectionResponse:
    """Create a new collection for the authenticated user."""
    return await CollectionService.create_collection(db, current_user.id, data)


@router.get(
    "",
    response_model=list[CollectionResponse],
)
async def list_collections(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CollectionResponse]:
    """Retrieve all collections belonging to the authenticated user."""
    return await CollectionService.list_collections(db, current_user.id)


@router.get(
    "/{id}",
    response_model=CollectionResponse,
)
async def get_collection(
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CollectionResponse:
    """Retrieve details of a specific collection by ID."""
    return await CollectionService.get_collection(db, current_user.id, id)


@router.patch(
    "/{id}",
    response_model=CollectionResponse,
)
async def update_collection(
    id: UUID,
    data: CollectionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CollectionResponse:
    """Update metadata of an existing collection."""
    return await CollectionService.update_collection(db, current_user.id, id, data)


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_collection(
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a collection belonging to the authenticated user."""
    await CollectionService.delete_collection(db, current_user.id, id)


@router.post(
    "/{id}/entries",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def add_entry_to_collection(
    id: UUID,
    data: CollectionEntryAdd,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Add a journal entry to a collection idempotently."""
    await CollectionService.add_entry_to_collection(
        db, current_user.id, id, data.journal_entry_id
    )


@router.delete(
    "/{id}/entries/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_entry_from_collection(
    id: UUID,
    entry_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a journal entry from a collection idempotently."""
    await CollectionService.remove_entry_from_collection(
        db, current_user.id, id, entry_id
    )
