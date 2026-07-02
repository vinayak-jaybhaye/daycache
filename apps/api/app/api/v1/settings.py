"""Settings API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, get_db
from app.db.models import User, UserSettings
from app.modules.settings.schemas import SettingsResponse, UpdateSettingsRequest
from app.modules.settings.service import SettingsService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get(
    "",
    response_model=SettingsResponse,
)
async def get_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserSettings:
    """Return the authenticated user's application settings."""
    return await SettingsService.get_settings(db=db, user_id=current_user.id)


@router.patch(
    "",
    response_model=SettingsResponse,
)
async def update_settings(
    data: UpdateSettingsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserSettings:
    """Partially update the authenticated user's application settings."""
    return await SettingsService.update_settings(
        db=db,
        user_id=current_user.id,
        data=data,
    )
