"""Users API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import get_current_user, get_db
from app.db.models import User
from app.modules.users.schemas import UpdateProfileRequest, UserProfileResponse
from app.modules.users.service import UserService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get(
    "/me",
    response_model=UserProfileResponse,
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> User:
    """Return the authenticated user's profile."""
    return current_user


@router.patch(
    "/me",
    response_model=UserProfileResponse,
)
async def update_me(
    data: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Partially update the authenticated user's mutable profile fields."""
    return await UserService.update_profile(
        db=db,
        user_id=current_user.id,
        data=data,
    )


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
