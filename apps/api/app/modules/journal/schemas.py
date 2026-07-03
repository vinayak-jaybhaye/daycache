"""Journal request and response schemas.

All Pydantic models for the journal feature live here.
No FastAPI imports — schemas are framework-agnostic.
"""

from __future__ import annotations

from datetime import date as date_type
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.tags.schemas import TagInfo


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


class JournalEntryUpdate(BaseModel):
    """Schema for updating an existing journal entry."""

    title: str | None = Field(None)
    content: dict[str, Any] | None = Field(None)
    is_favorite: bool | None = Field(None)
    tag_ids: list[UUID] | None = Field(None)
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

    class Config:
        from_attributes = True


class PaginatedJournalEntriesResponse(BaseModel):
    """Schema representing a paginated journal entries list."""

    items: list[JournalEntryResponse]
    total: int
    next_cursor: str | None = None


class LinkTagRequest(BaseModel):
    """Request schema for associating a tag with an entry."""

    tag_id: UUID = Field(..., description="The ID of the Tag to link")
