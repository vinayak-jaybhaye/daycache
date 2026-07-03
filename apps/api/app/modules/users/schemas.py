"""Users module schemas for request validation and response serialisation."""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserProfileResponse(BaseModel):
    """Authenticated user's account/profile information.

    Excludes authentication metadata (sessions, devices, password state).
    ``avatar_url`` is a short-lived signed read URL resolved dynamically
    from the linked avatar media record's thumbnail; it is ``None`` when
    no avatar has been set or the media has not yet finished processing.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    display_name: str
    avatar_url: str | None = None
    created_at: datetime
    updated_at: datetime


class UpdateProfileRequest(BaseModel):
    """Partial update payload for mutable profile fields.

    Only fields that are present in the request body are updated.
    Omitted fields are left unchanged.
    """

    display_name: str | None = Field(None, min_length=2, max_length=50)


class AvatarUploadRequest(BaseModel):
    """Payload to request a presigned avatar upload URL.

    The client declares the file size and MIME type upfront so the server
    can validate before issuing a presigned URL.  Accepted MIME types are
    ``image/jpeg``, ``image/png``, and ``image/webp``.  Maximum size is 5 MB.
    """

    _ALLOWED_MIMES: ClassVar[frozenset[str]] = frozenset(
        {"image/jpeg", "image/png", "image/webp"}
    )
    _MAX_BYTES: ClassVar[int] = 5 * 1024 * 1024  # 5 MB

    mime_type: str = Field(..., max_length=100)
    size: int = Field(..., gt=0, description="Declared file size in bytes.")

    @field_validator("mime_type")
    @classmethod
    def validate_mime_type(cls, v: str) -> str:
        if v not in cls._ALLOWED_MIMES:
            allowed = ", ".join(sorted(cls._ALLOWED_MIMES))
            raise ValueError(f"Unsupported MIME type. Allowed: {allowed}")
        return v

    @field_validator("size")
    @classmethod
    def validate_size(cls, v: int) -> int:
        if v > cls._MAX_BYTES:
            raise ValueError(
                f"File size exceeds the 5 MB limit ({v} > {cls._MAX_BYTES} bytes)."
            )
        return v
