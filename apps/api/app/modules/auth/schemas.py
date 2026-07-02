"""Authentication schemas for request validation and response serialisation."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.db.enums import DevicePlatform


class UserRegisterRequest(BaseModel):
    """Payload to register a new email/password account."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    display_name: str = Field(..., min_length=2, max_length=50)


class UserLoginRequest(BaseModel):
    """Payload to authenticate and resolve a device session."""

    email: EmailStr
    password: str
    device_identifier: str = Field(..., min_length=1, max_length=200)
    device_name: str | None = Field(None, max_length=100)
    platform: DevicePlatform


class UserResponse(BaseModel):
    """User account metadata returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    display_name: str
    avatar_key: str | None
    is_verified: bool
    created_at: datetime


class SessionResponse(BaseModel):
    """Active session metadata representing a logged-in device."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    device_name: str | None
    device_platform: DevicePlatform
    ip_address: str | None
    user_agent: str | None
    last_used_at: datetime
    created_at: datetime
    is_current: bool


class DeviceSessionResponse(BaseModel):
    """A session running on a specific device."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ip_address: str | None
    user_agent: str | None
    last_used_at: datetime
    is_current: bool


class DeviceResponse(BaseModel):
    """User device registrations grouped with their active sessions."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str | None
    platform: DevicePlatform
    last_seen_at: datetime
    created_at: datetime
    is_current: bool
    sessions: list[DeviceSessionResponse]
