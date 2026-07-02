"""Users module schemas for request validation and response serialisation."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UserProfileResponse(BaseModel):
    """Authenticated user's account/profile information.

    Excludes authentication metadata (sessions, devices, password state).
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    display_name: str
    avatar_key: str | None
    created_at: datetime
    updated_at: datetime


class UpdateProfileRequest(BaseModel):
    """Partial update payload for mutable profile fields.

    Only fields that are present in the request body are updated.
    Omitted fields are left unchanged.

    Note: avatar_key is intentionally excluded. Avatars are managed
    server-side through the media upload flow.
    """

    display_name: str | None = Field(None, min_length=2, max_length=50)
