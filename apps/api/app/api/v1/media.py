"""Media API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.deps import get_current_user, get_db, get_settings
from app.db.models import User
from app.modules.media.schemas import (
    MediaStatusResponse,
    MediaUploadRequest,
    MediaUploadResponse,
)
from app.modules.media.service import MediaService
from app.storage.factory import get_storage

if TYPE_CHECKING:
    from arq import ArqRedis
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.core.config import Settings
    from app.storage.base import StorageBackend

router = APIRouter()


async def get_arq_pool() -> ArqRedis:
    """Return the shared ARQ Redis pool for job enqueueing."""
    from arq import create_pool
    from arq.connections import RedisSettings

    from app.core.config import get_settings as _get_settings

    settings = _get_settings()
    return await create_pool(RedisSettings.from_dsn(str(settings.REDIS_URL)))


@router.post(
    "/upload",
    response_model=MediaUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def request_upload(
    data: MediaUploadRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
    settings: Settings = Depends(get_settings),
) -> MediaUploadResponse:
    """Request a presigned upload URL and create a PENDING media record."""
    return await MediaService.request_upload(
        db=db,
        storage=storage,
        user_id=current_user.id,
        data=data,
        settings=settings,
    )


@router.post(
    "/{media_id}/confirm",
    response_model=MediaStatusResponse,
)
async def confirm_upload(
    media_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
    arq_pool: ArqRedis = Depends(get_arq_pool),
) -> MediaStatusResponse:
    """Confirm a completed upload and enqueue the processing job.

    Returns 410 if the upload TTL has expired.
    Returns 422 if the object is not present in storage.
    """
    return await MediaService.confirm_upload(
        db=db,
        storage=storage,
        arq_pool=arq_pool,
        user_id=current_user.id,
        media_id=media_id,
    )


@router.get(
    "/{media_id}",
    response_model=MediaStatusResponse,
)
async def get_media(
    media_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
    settings: Settings = Depends(get_settings),
) -> MediaStatusResponse:
    """Return the current status and signed read URLs for a media record."""
    return await MediaService.get_media(
        db=db,
        storage=storage,
        user_id=current_user.id,
        media_id=media_id,
        settings=settings,
    )


@router.delete(
    "/{media_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_media(
    media_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
) -> None:
    """Delete a media record and its storage objects."""
    await MediaService.delete_media(
        db=db,
        storage=storage,
        user_id=current_user.id,
        media_id=media_id,
    )
