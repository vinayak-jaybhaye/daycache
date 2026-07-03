"""User and Settings domain models."""

from __future__ import annotations

from datetime import time
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, SmallInteger, Text, Time
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.db.models.ai import Embedding, Summary
    from app.db.models.auth import Device, OAuthAccount
    from app.db.models.journal import Day
    from app.db.models.media import Media
    from app.db.models.organization import Collection, Tag


class User(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    """User account entity.

    email is compared case-insensitively using CITEXT.
    """

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_media_id: Mapped[str | None] = mapped_column(
        PGUUID(as_uuid=False),
        ForeignKey("media.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    settings: Mapped[UserSettings] = relationship(
        "UserSettings",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    oauth_accounts: Mapped[list[OAuthAccount]] = relationship(
        "OAuthAccount",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    devices: Mapped[list[Device]] = relationship(
        "Device",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    days: Mapped[list[Day]] = relationship(
        "Day",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    tags: Mapped[list[Tag]] = relationship(
        "Tag",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    collections: Mapped[list[Collection]] = relationship(
        "Collection",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    media: Mapped[list[Media]] = relationship(
        "Media",
        foreign_keys="[Media.user_id]",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    summaries: Mapped[list[Summary]] = relationship(
        "Summary",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    embeddings: Mapped[list[Embedding]] = relationship(
        "Embedding",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class UserSettings(TimestampMixin, Base):
    """User preference settings entity.

    One-to-one relationship with User.
    """

    __tablename__ = "user_settings"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    locale: Mapped[str] = mapped_column(Text, default="en-US", nullable=False)
    timezone: Mapped[str] = mapped_column(Text, default="UTC", nullable=False)
    theme: Mapped[str] = mapped_column(Text, default="system", nullable=False)
    week_starts_on: Mapped[int] = mapped_column(
        SmallInteger,
        default=1,
        nullable=False,
    )
    default_reminder_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    editor_font: Mapped[str] = mapped_column(Text, default="inter", nullable=False)
    content_language: Mapped[str] = mapped_column(Text, default="en", nullable=False)

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="settings")

    __table_args__ = (
        CheckConstraint(
            "week_starts_on BETWEEN 0 AND 6",
            name="week_starts_on_check",
        ),
    )
