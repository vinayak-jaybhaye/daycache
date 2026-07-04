"""AI feature request and response schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_serializer, model_validator

from app.db.enums import SummaryKind, SummaryScope


class SummaryOutput(BaseModel):
    """Structured output expected from the LLM provider."""

    content: str
    highlights: list[str]
    challenges: list[str]
    themes: list[str]
    mood_analysis: dict[str, Any] | None = None


class SummaryResponse(BaseModel):
    """Schema representing an AI-generated summary response."""

    id: UUID
    user_id: UUID
    scope: SummaryScope
    kind: SummaryKind
    journal_entry_id: UUID | None
    day_id: UUID | None
    period_start: date | None
    period_end: date | None
    content: str
    highlights: list[str] | None
    challenges: list[str] | None
    themes: list[str] | None
    mood_analysis: dict[str, Any] | None
    provider: str
    model: str
    prompt_version: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @model_serializer(mode="wrap")
    def serialize_by_scope(self, handler: Any) -> dict[str, Any]:
        data = handler(self)
        # Drop unwanted fields always
        for field in ["user_id", "provider", "model", "prompt_version"]:
            data.pop(field, None)

        # Conditionally drop based on scope
        scope = data.get("scope")
        if scope != SummaryScope.ENTRY:
            data.pop("journal_entry_id", None)
        if scope != SummaryScope.DAY:
            data.pop("day_id", None)
        if scope not in (
            SummaryScope.WEEK,
            SummaryScope.MONTH,
            SummaryScope.YEAR,
        ):
            data.pop("period_start", None)
            data.pop("period_end", None)

        return data


class SummaryCreateInternal(BaseModel):
    """Internal model for validating and creating a new Summary aggregate."""

    user_id: UUID
    scope: SummaryScope
    kind: SummaryKind = SummaryKind.SUMMARY
    journal_entry_id: UUID | None = None
    day_id: UUID | None = None
    period_start: date | None = None
    period_end: date | None = None

    @model_validator(mode="after")
    def validate_reference(self) -> Self:
        match self.scope:
            case SummaryScope.ENTRY:
                if not self.journal_entry_id:
                    raise ValueError("journal_entry_id required for scope=entry")
            case SummaryScope.DAY:
                if not self.day_id:
                    raise ValueError("day_id required for scope=day")
            case SummaryScope.WEEK | SummaryScope.MONTH | SummaryScope.YEAR:
                if not (self.period_start and self.period_end):
                    raise ValueError(
                        "period_start and period_end required for scope=week/month/year"
                    )
        return self
