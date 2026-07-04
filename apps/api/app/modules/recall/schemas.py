"""Recall feature API schemas."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RetrievedEntryMetadata(BaseModel):
    """Citation metadata for entries retrieved as context for an assistant message."""

    entry_id: UUID
    entry_title: str | None = None
    day_date: date
    score: float

    model_config = ConfigDict(from_attributes=True)


class RecallMessageResponse(BaseModel):
    """Schema representing an individual interaction turn in a Recall session."""

    id: UUID
    role: str
    content: str
    retrieved_entries: list[RetrievedEntryMetadata] | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RecallSessionResponse(BaseModel):
    """Schema representing Recall session metadata."""

    id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MessageCreate(BaseModel):
    """Schema for sending a new message to the Recall session."""

    content: str = Field(
        ...,
        min_length=10,
        description="The content of the query to Recall. Must be at least 10 characters.",
    )
