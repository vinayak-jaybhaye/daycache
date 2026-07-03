"""Journal request and response schemas.

All Pydantic models for the journal feature live here.
No FastAPI imports — schemas are framework-agnostic.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class JournalEntryResponse(BaseModel):
    """Schema representing a journal entry."""

    id: UUID
    day_id: UUID
    title: str | None
    content: dict[str, Any]
    content_text: str | None
    word_count: int
    is_draft: bool
    is_favorite: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
