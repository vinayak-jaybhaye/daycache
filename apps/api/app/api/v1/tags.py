"""Tags API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.deps import get_current_user, get_db
from app.db.models import User
from app.modules.tags.schemas import TagCreate, TagResponse, TagUpdate
from app.modules.tags.service import TagService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.post(
    "",
    response_model=TagResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_tag(
    data: TagCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TagResponse:
    """Create a new tag for the authenticated user."""
    return await TagService.create_tag(db, current_user.id, data)


@router.get(
    "",
    response_model=list[TagResponse],
)
async def list_tags(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TagResponse]:
    """Retrieve all tags belonging to the authenticated user."""
    return await TagService.list_tags(db, current_user.id)


@router.get(
    "/{id}",
    response_model=TagResponse,
)
async def get_tag(
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TagResponse:
    """Retrieve details of a specific tag by ID."""
    return await TagService.get_tag(db, current_user.id, id)


@router.patch(
    "/{id}",
    response_model=TagResponse,
)
async def update_tag(
    id: UUID,
    data: TagUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TagResponse:
    """Update metadata of an existing tag."""
    return await TagService.update_tag(db, current_user.id, id, data)


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_tag(
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a tag belonging to the authenticated user."""
    await TagService.delete_tag(db, current_user.id, id)
