"""Users API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import get_arq_pool, get_current_user, get_db, get_settings
from app.db.models import User
from app.modules.media.schemas import MediaUploadResponse
from app.modules.settings.schemas import SettingsResponse, UpdateSettingsRequest
from app.modules.settings.service import SettingsService
from app.modules.users.schemas import (
    AvatarUploadRequest,
    UpdateProfileRequest,
    UserProfileResponse,
)
from app.modules.users.service import UserService
from app.storage.factory import get_storage

if TYPE_CHECKING:
    from arq import ArqRedis
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.core.config import Settings
    from app.storage.base import StorageBackend

router = APIRouter()


@router.get(
    "/me",
    response_model=UserProfileResponse,
)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
) -> UserProfileResponse:
    """Return the authenticated user's profile."""
    return await UserService.build_profile_response(db, current_user, storage)


@router.patch(
    "/me",
    response_model=UserProfileResponse,
)
async def update_me(
    data: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
) -> UserProfileResponse:
    """Partially update the authenticated user's mutable profile fields."""
    user = await UserService.update_profile(
        db=db,
        user_id=current_user.id,
        data=data,
    )
    return await UserService.build_profile_response(db, user, storage)


@router.post(
    "/me/avatar",
    response_model=MediaUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def request_avatar_upload(
    data: AvatarUploadRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
    settings: Settings = Depends(get_settings),
) -> MediaUploadResponse:
    """Request a presigned PUT URL to upload a new avatar image.

    Creates a media record under the server-controlled ``avatars/`` storage
    prefix.  The client must PUT the image bytes to ``upload_url`` and then
    call ``POST /me/avatar/confirm`` to activate the new avatar.
    """
    media_id, upload_url, upload_expires_at = await UserService.request_avatar_upload(
        db=db,
        storage=storage,
        user_id=current_user.id,
        mime_type=data.mime_type,
        size=data.size,
        settings=settings,
    )
    return MediaUploadResponse(
        media_id=media_id,
        upload_url=upload_url,
        upload_expires_at=upload_expires_at,
    )


@router.post(
    "/me/avatar/confirm",
    response_model=UserProfileResponse,
)
async def confirm_avatar_upload(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
    arq_pool: ArqRedis = Depends(get_arq_pool),
    settings: Settings = Depends(get_settings),
) -> UserProfileResponse:
    """Confirm the avatar upload and enqueue background processing.

    No request body needed — the server finds the most recent pending
    avatar upload for this user automatically.  Call this after completing
    the presigned PUT request returned by ``POST /me/avatar``.
    """
    user = await UserService.confirm_avatar_upload(
        db=db,
        storage=storage,
        arq_pool=arq_pool,
        user=current_user,
        settings=settings,
    )
    return await UserService.build_profile_response(db, user, storage)


@router.delete(
    "/me/avatar",
    response_model=UserProfileResponse,
)
async def remove_avatar(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
) -> UserProfileResponse:
    user = await UserService.remove_avatar(db=db, user=current_user, storage=storage)
    return await UserService.build_profile_response(db, user, storage)


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_me(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft-delete the authenticated user account and revoke all sessions."""
    await UserService.delete_account(db=db, user_id=current_user.id)


@router.get(
    "/me/settings",
    response_model=SettingsResponse,
)
async def get_my_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SettingsResponse:
    """Return the authenticated user's application settings."""
    settings_orm = await SettingsService.get_settings(db=db, user_id=current_user.id)
    return SettingsResponse.model_validate(settings_orm)


@router.patch(
    "/me/settings",
    response_model=SettingsResponse,
)
async def update_my_settings(
    data: UpdateSettingsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SettingsResponse:
    """Partially update the authenticated user's application settings."""
    settings_orm = await SettingsService.update_settings(
        db=db,
        user_id=current_user.id,
        data=data,
    )
    return SettingsResponse.model_validate(settings_orm)
