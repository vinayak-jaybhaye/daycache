"""Tag domain models."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDMixin

if TYPE_CHECKING:
    from app.db.models.journal import JournalEntry
    from app.db.models.user import User


class Tag(UUIDMixin, Base):
    """User-defined label that can be assigned to multiple journal entries."""

    __tablename__ = "tags"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    color: Mapped[str] = mapped_column(Text, default="#7C6EE6", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="tags")
    entries: Mapped[list[JournalEntry]] = relationship(
        "JournalEntry",
        secondary="journal_tags",
        back_populates="tags",
    )

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="tags_user_id_name_key"),
        CheckConstraint("name = lower(name)", name="tags_name_lower_check"),
        Index("idx_tags_user_id", "user_id"),
    )


class JournalTag(Base):
    """Many-to-many association mapping JournalEntry and Tag."""

    __tablename__ = "journal_tags"

    journal_entry_id: Mapped[str] = mapped_column(
        ForeignKey("journal_entries.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id: Mapped[str] = mapped_column(
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    )

    __table_args__ = (
        Index("idx_journal_tags_entry", "journal_entry_id"),
        Index("idx_journal_tags_tag", "tag_id"),
    )
