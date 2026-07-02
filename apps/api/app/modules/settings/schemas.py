"""Settings module schemas for request validation and response serialisation."""

from __future__ import annotations

import zoneinfo
from datetime import datetime, time
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

# BCP 47 locale tag: language code (2-3 chars) with optional region subtag.
# Valid examples: "en", "en-US", "zh-CN", "pt-BR", "fr-FR"
_LOCALE_RE = r"^[a-z]{2,3}(-[A-Z]{2,3})?$"

# ISO 639-1/639-2 language code only — no region subtag.
# Valid examples: "en", "fr", "zh", "pt"
_LANGUAGE_RE = r"^[a-z]{2,3}$"

# Validated against the IANA timezone database bundled with Python's zoneinfo.
_VALID_TIMEZONES: frozenset[str] = frozenset(zoneinfo.available_timezones())

# Closed set of UI themes supported by the client.
Theme = Literal["light", "dark", "system"]


class SettingsResponse(BaseModel):
    """Full user settings payload returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    locale: str
    timezone: str
    theme: str
    week_starts_on: int
    default_reminder_time: time | None
    ai_enabled: bool
    editor_font: str
    content_language: str
    updated_at: datetime


class UpdateSettingsRequest(BaseModel):
    """Partial update payload for user settings.

    Only fields present in the request body are applied; omitted fields
    retain their current database values.
    """

    locale: Annotated[str, Field(pattern=_LOCALE_RE)] | None = None
    timezone: str | None = Field(None, max_length=100)
    theme: Theme | None = None
    week_starts_on: int | None = Field(None, ge=0, le=6)
    default_reminder_time: time | None = None
    ai_enabled: bool | None = None
    editor_font: str | None = Field(None, max_length=50)
    content_language: Annotated[str, Field(pattern=_LANGUAGE_RE)] | None = None

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str | None) -> str | None:
        """Reject timezone strings not present in the IANA timezone database.

        Args:
            v: Timezone string to validate, e.g. ``"America/New_York"``.

        Returns:
            The original value if valid.

        Raises:
            ValueError: If the timezone is not a recognised IANA identifier.
        """
        if v is not None and v not in _VALID_TIMEZONES:
            raise ValueError(
                f"'{v}' is not a valid IANA timezone identifier. "
                "Use a value such as 'America/New_York' or 'Asia/Kolkata'."
            )
        return v
