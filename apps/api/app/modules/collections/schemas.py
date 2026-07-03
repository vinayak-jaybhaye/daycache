"""Collection schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class CollectionCreate(BaseModel):
    """Schema for collection creation requests."""

    name: str = Field(..., min_length=1, description="Unique label for the collection")
    description: str | None = Field(None, description="Optional collection description")
    icon: str | None = Field(
        None, description="Optional icon plain text (emoji or keyword)"
    )
    is_pinned: bool = Field(False, description="Whether the collection is pinned")

    @field_validator("name")
    @classmethod
    def normalize_name(cls, v: str) -> str:
        v = v.strip().lower()
        if not v:
            raise ValueError("Collection name cannot be empty")
        return v


class CollectionUpdate(BaseModel):
    """Schema for collection update requests."""

    name: str | None = Field(None, min_length=1)
    description: str | None = Field(None)
    icon: str | None = Field(None)
    is_pinned: bool | None = Field(None)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip().lower()
            if not v:
                raise ValueError("Collection name cannot be empty")
        return v


class CollectionResponse(BaseModel):
    """Schema for collection response objects."""

    id: UUID
    name: str
    description: str | None
    icon: str | None
    is_pinned: bool
    entry_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CollectionEntryAdd(BaseModel):
    """Schema for adding an entry to a collection."""

    journal_entry_id: UUID
