"""Journal Core domain models."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.db.models.ai import JournalChunk, Summary
    from app.db.models.media import Media
    from app.db.models.mood import EntryMood
    from app.db.models.organization import Collection, Tag
    from app.db.models.user import User


class Day(UUIDMixin, TimestampMixin, Base):
    """Aggregate entity representing a single calendar day for a User.

    Contains metadata like weather and location observed on entry creation.
    """

    __tablename__ = "days"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    weather: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    location: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="days")
    entries: Mapped[list[JournalEntry]] = relationship(
        "JournalEntry",
        back_populates="day",
        cascade="all, delete-orphan",
    )
    summaries: Mapped[list[Summary]] = relationship(
        "Summary",
        back_populates="day",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("user_id", "date", name="days_user_id_date_key"),
        Index("idx_days_user_date", "user_id", text("date DESC")),
    )


class JournalEntry(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    """Individual journal entry containing rich text document and metadata."""

    __tablename__ = "journal_entries"

    day_id: Mapped[UUID] = mapped_column(
        ForeignKey("days.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        server_default=text("'{}'::JSONB"),
        nullable=False,
    )
    content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    word_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    search_vector: Mapped[Any] = mapped_column(TSVECTOR, nullable=True)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    version: Mapped[int] = mapped_column(
        Integer, server_default=text("1"), default=1, nullable=False
    )

    __mapper_args__: dict[str, Any] = {"version_id_col": version}  # noqa: RUF012

    # Relationships
    day: Mapped[Day] = relationship("Day", back_populates="entries")

    # Many-to-many relationships
    tags: Mapped[list[Tag]] = relationship(
        "Tag",
        secondary="journal_tags",
        back_populates="entries",
    )
    collections: Mapped[list[Collection]] = relationship(
        "Collection",
        secondary="collection_entries",
        back_populates="entries",
    )
    moods: Mapped[list[EntryMood]] = relationship(
        "EntryMood",
        back_populates="journal_entry",
        cascade="all, delete-orphan",
    )
    media: Mapped[list[Media]] = relationship(
        "Media",
        secondary="journal_media",
        back_populates="journal_entries",
    )
    chunks: Mapped[list[JournalChunk]] = relationship(
        "JournalChunk",
        back_populates="journal_entry",
        cascade="all, delete-orphan",
    )
    summaries: Mapped[list[Summary]] = relationship(
        "Summary",
        back_populates="journal_entry",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_entries_day_id", "day_id"),
        Index(
            "idx_entries_active",
            "day_id",
            text("created_at DESC"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "idx_entries_favorite",
            "day_id",
            postgresql_where=text("is_favorite = TRUE AND deleted_at IS NULL"),
        ),
        Index(
            "idx_entries_search",
            "search_vector",
            postgresql_using="gin",
        ),
        Index(
            "idx_entries_title_trgm",
            text("title gin_trgm_ops"),
            postgresql_using="gin",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )
