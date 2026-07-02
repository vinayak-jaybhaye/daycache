"""Media (attachments, images, videos) domain models."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, Text, text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.db.enums import MediaProcessingStatus, MediaType

if TYPE_CHECKING:
    from app.db.models.journal import JournalEntry
    from app.db.models.user import User


class Media(UUIDMixin, TimestampMixin, Base):
    """Media asset metadata (stored in object storage)."""

    __tablename__ = "media"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    storage_key: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    thumbnail_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_type: Mapped[MediaType] = mapped_column(
        SQLEnum("image", "video", name="media_type"),
        nullable=False,
    )
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    color_palette: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    blurhash: Mapped[str | None] = mapped_column(Text, nullable=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    alt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    processing_status: Mapped[MediaProcessingStatus] = mapped_column(
        SQLEnum(
            "pending",
            "processing",
            "completed",
            "failed",
            name="media_processing_status",
        ),
        default=MediaProcessingStatus.PENDING,
        nullable=False,
    )
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        server_default=text("'{}'::JSONB"),
        nullable=False,
    )

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="media")
    journal_entries: Mapped[list[JournalEntry]] = relationship(
        "JournalEntry",
        secondary="journal_media",
        back_populates="media",
    )

    __table_args__ = (
        Index("idx_media_user_id", "user_id"),
        Index(
            "idx_media_pending",
            "processing_status",
            postgresql_where=text("processing_status IN ('pending', 'processing')"),
        ),
    )


class JournalMedia(Base):
    """Junction mapping JournalEntry and Media with custom sorting/positioning."""

    __tablename__ = "journal_media"

    journal_entry_id: Mapped[str] = mapped_column(
        ForeignKey("journal_entries.id", ondelete="CASCADE"),
        primary_key=True,
    )
    media_id: Mapped[str] = mapped_column(
        ForeignKey("media.id", ondelete="CASCADE"),
        primary_key=True,
    )
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    __table_args__ = (Index("idx_journal_media_entry", "journal_entry_id"),)
