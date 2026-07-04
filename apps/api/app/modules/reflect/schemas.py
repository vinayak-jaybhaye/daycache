"""Reflect feature API schemas."""

from __future__ import annotations

from datetime import date as date_type
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ReflectMessageResponse(BaseModel):
    """Schema representing an individual interaction turn in a Reflect session."""

    id: UUID
    role: str
    content: str
    date: date_type
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReflectSessionResponse(BaseModel):
    """Schema representing Reflect session metadata."""

    id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReflectMessageCreate(BaseModel):
    """Schema for sending a new message to the Reflect session."""

    content: str = Field(
        ...,
        min_length=1,
        description="The message to Reflect. Must not be empty.",
    )
