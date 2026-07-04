"""AI feature request and response schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Self
from uuid import UUID

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    model_serializer,
    model_validator,
)

from app.db.enums import SummaryKind, SummaryScope


class MoodBreakdownItem(BaseModel):
    mood: str
    count: int


class MoodAnalysisOutput(BaseModel):
    trend: str = Field(description="improving / stable / declining / unknown")
    average: float | None = Field(
        None,
        validation_alias=AliasChoices("average", "average_intensity"),
        description="Average emotional intensity, numeric between 1.0 and 10.0",
    )
    breakdown: list[MoodBreakdownItem] = Field(default_factory=list)


class SummaryOutput(BaseModel):
    """Structured output expected from the LLM provider."""

    content: str = Field(
        validation_alias=AliasChoices("content", "Content", "summary", "Summary")
    )
    highlights: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices(
            "highlights", "Highlights", "highlight", "Highlight"
        ),
    )
    challenges: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices(
            "challenges", "Challenges", "challenge", "Challenge"
        ),
    )
    themes: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("themes", "Themes", "theme", "Theme"),
    )
    mood_analysis: MoodAnalysisOutput | None = Field(
        default=None,
        validation_alias=AliasChoices("mood_analysis", "MoodAnalysis", "mood", "Mood"),
    )

    @model_validator(mode="before")
    @classmethod
    def heal_keys(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        # 1. Normalize aliases or heal missing fields
        # Check if content is missing
        content_aliases = {"content", "Content", "summary", "Summary"}
        has_content = any(k in data for k in content_aliases)
        if not has_content:
            # Pick the longest string value that is not map/list
            str_candidates = [v for _, v in data.items() if isinstance(v, str)]
            if str_candidates:
                data["content"] = max(str_candidates, key=len)

        # 2. Heal lists if they are missing or null
        for field in ("highlights", "challenges", "themes"):
            field_aliases = {
                field,
                field.capitalize(),
                field.rstrip("s"),
                field.rstrip("s").capitalize(),
            }
            # Check if any alias is present
            found_key = None
            for key in data:
                if key in field_aliases:
                    found_key = key
                    break

            if found_key is not None:
                # Ensure the value is a list of strings
                val = data[found_key]
                if val is None:
                    data[found_key] = []
                elif isinstance(val, str):
                    data[found_key] = [val]
                elif not isinstance(val, list):
                    data[found_key] = []
            else:
                data[field] = []

        return data


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
