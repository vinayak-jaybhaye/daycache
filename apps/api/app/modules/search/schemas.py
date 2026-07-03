"""Search request and response schemas.

All Pydantic models for the search feature live here.
No FastAPI imports — schemas are framework-agnostic.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.modules.journal.schemas import JournalEntryResponse


class SearchResultItem(BaseModel):
    """Schema representing a single search result item."""

    entry: JournalEntryResponse
    score: float
    match_type: Literal["keyword", "semantic", "hybrid"]
    highlight_snippet: str | None = None

    model_config = ConfigDict(from_attributes=True)
