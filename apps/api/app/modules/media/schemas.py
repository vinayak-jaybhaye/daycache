"""Media module schemas for request validation and response serialisation."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.db.enums import MediaProcessingStatus, MediaType, MediaUploadStatus

# Allowed MIME types per media type.
_ALLOWED_IMAGE_MIMES = frozenset(["image/jpeg", "image/png", "image/gif", "image/webp"])
_ALLOWED_VIDEO_MIMES = frozenset(["video/mp4", "video/quicktime", "video/webm"])


class MediaUploadRequest(BaseModel):
    """Payload to request a presigned upload URL."""

    media_type: MediaType
    mime_type: str = Field(..., max_length=100)
    filename: str = Field(..., min_length=1, max_length=255)
    size: int = Field(..., gt=0, description="File size in bytes.")

    def validate_mime_for_type(self) -> None:
        """Raise ValueError if mime_type is not allowed for the given media_type.

        Called from the service layer after construction so errors are
        surfaced as UnprocessableError, not Pydantic validation errors.
        """
        if (
            self.media_type == MediaType.IMAGE
            and self.mime_type not in _ALLOWED_IMAGE_MIMES
        ):
            allowed = ", ".join(sorted(_ALLOWED_IMAGE_MIMES))
            raise ValueError(f"Unsupported image MIME type. Allowed: {allowed}")
        if (
            self.media_type == MediaType.VIDEO
            and self.mime_type not in _ALLOWED_VIDEO_MIMES
        ):
            allowed = ", ".join(sorted(_ALLOWED_VIDEO_MIMES))
            raise ValueError(f"Unsupported video MIME type. Allowed: {allowed}")


class MediaUploadResponse(BaseModel):
    """Response after successfully requesting a presigned upload URL."""

    model_config = ConfigDict(from_attributes=True)

    media_id: UUID
    upload_url: str
    upload_expires_at: datetime


class MediaStatusResponse(BaseModel):
    """Media record with current state and signed read URLs."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    media_type: MediaType
    mime_type: str
    size: int
    upload_status: MediaUploadStatus
    processing_status: MediaProcessingStatus | None
    width: int | None
    height: int | None
    duration_seconds: int | None
    blurhash: str | None
    caption: str | None
    alt_text: str | None
    created_at: datetime
    # Signed read URLs — populated only when processing_status == COMPLETED.
    read_url: str | None = None
    thumbnail_url: str | None = None
