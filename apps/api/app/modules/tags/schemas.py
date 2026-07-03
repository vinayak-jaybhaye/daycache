"""Tag schemas."""

from __future__ import annotations

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class TagCreate(BaseModel):
    """Schema for tag creation requests."""

    name: str = Field(..., min_length=1, description="Unique label for the tag")
    color: str = Field("#7C6EE6", description="HEX color code starting with #")

    @field_validator("name")
    @classmethod
    def normalize_name(cls, v: str) -> str:
        v = v.strip().lower()
        if not v:
            raise ValueError("Tag name cannot be empty")
        return v

    @field_validator("color")
    @classmethod
    def validate_hex_color(cls, v: str) -> str:
        if not re.match(r"^#[0-9a-fA-F]{3}([0-9a-fA-F]{3})?$", v):
            raise ValueError(
                "Color must be a valid hex color string (e.g. #7C6EE6 or #FFF)"
            )
        return v


class TagUpdate(BaseModel):
    """Schema for tag update requests."""

    name: str | None = Field(None, min_length=1)
    color: str | None = Field(None)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip().lower()
            if not v:
                raise ValueError("Tag name cannot be empty")
        return v

    @field_validator("color")
    @classmethod
    def validate_hex_color(cls, v: str | None) -> str | None:
        if v is not None and not re.match(r"^#[0-9a-fA-F]{3}([0-9a-fA-F]{3})?$", v):
            raise ValueError(
                "Color must be a valid hex color string (e.g. #7C6EE6 or #FFF)"
            )
        return v


class TagInfo(BaseModel):
    """Simplified tag schema for nested listings."""

    id: UUID
    name: str
    color: str
    created_at: datetime

    class Config:
        from_attributes = True


class TagResponse(TagInfo):
    """Schema for tag response objects with entry counts."""

    entry_count: int
