"""Journal request and response schemas.

All Pydantic models for the journal feature live here.
No FastAPI imports — schemas are framework-agnostic.
"""

from __future__ import annotations

from datetime import date as date_type
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.modules.media.schemas import MediaStatusResponse
from app.modules.tags.schemas import TagInfo


class LinkMediaRequest(BaseModel):
    """Request schema for associating a media asset with an entry."""

    media_id: UUID = Field(..., description="The ID of the Media to link")
    position: int = Field(
        0, ge=0, description="Sorting position of the media in the entry"
    )


class MoodResponse(BaseModel):
    """Schema representing a predefined system mood."""

    id: UUID
    name: str
    color: str

    class Config:
        from_attributes = True


class EntryMoodResponse(BaseModel):
    """Schema representing a mood linked to a specific journal entry."""

    id: UUID
    name: str
    color: str
    intensity: int

    class Config:
        from_attributes = True


class DayResponse(BaseModel):
    """Schema representing daily aggregate metadata."""

    id: UUID
    date: date_type
    location: dict[str, Any] | None
    weather: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DayUpdate(BaseModel):
    """Schema for updating daily aggregate metadata."""

    location: dict[str, Any] | None = None
    weather: dict[str, Any] | None = None


class JournalEntryCreate(BaseModel):
    """Schema for creating a new journal entry."""

    date: date_type = Field(..., description="Calendar date for this entry")
    title: str | None = Field(None, description="Optional title")
    content: dict[str, Any] = Field(
        default_factory=dict, description="Rich document content JSON"
    )
    is_favorite: bool = Field(
        False, description="Whether this entry is marked as favorite"
    )
    tag_ids: list[UUID] = Field(
        default_factory=list, description="Optional tag associations"
    )
    media_ids: list[UUID] = Field(
        default_factory=list, description="Optional initial media associations"
    )


class JournalEntryUpdate(BaseModel):
    """Schema for updating an existing journal entry."""

    title: str | None = Field(None)
    content: dict[str, Any] | None = Field(None)
    is_favorite: bool | None = Field(None)
    tag_ids: list[UUID] | None = Field(None)
    media_ids: list[UUID] | None = Field(None)
    version: int = Field(..., description="Current version of the entry in the client")


class JournalEntryResponse(BaseModel):
    """Schema representing a journal entry."""

    id: UUID
    day_id: UUID
    title: str | None
    content: dict[str, Any]
    content_text: str | None
    word_count: int
    is_favorite: bool
    version: int
    created_at: datetime

    updated_at: datetime
    tags: list[TagInfo] = Field(default_factory=list)
    moods: list[EntryMoodResponse] = Field(default_factory=list)
    media: list[MediaStatusResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True

    @model_validator(mode="before")
    @classmethod
    def ignore_lazy_relations(cls, data: Any) -> Any:
        from app.db.models.journal import JournalEntry

        if isinstance(data, JournalEntry):
            d: dict[str, Any] = {
                "id": data.id,
                "day_id": data.day_id,
                "title": data.title,
                "content": data.content,
                "content_text": data.content_text,
                "word_count": data.word_count,
                "is_favorite": data.is_favorite,
                "version": data.version,
                "created_at": data.created_at,
                "updated_at": data.updated_at,
            }
            if "tags" in data.__dict__:
                d["tags"] = data.tags
            if "moods" in data.__dict__:
                d["moods"] = data.moods
            if "media" in data.__dict__:
                d["media"] = data.media
            return d
        return data


class PaginatedJournalEntriesResponse(BaseModel):
    """Schema representing a paginated journal entries list."""

    items: list[JournalEntryResponse]
    total: int
    next_cursor: str | None = None


class LinkTagRequest(BaseModel):
    """Request schema for associating a tag with an entry."""

    tag_id: UUID = Field(..., description="The ID of the Tag to link")


class LinkMoodRequest(BaseModel):
    """Request schema for associating a mood with an entry."""

    mood_id: UUID = Field(..., description="The ID of the Mood to link")
    intensity: int = Field(5, ge=1, le=10, description="Mood intensity score (1-10)")
