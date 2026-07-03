"""Collection domain models."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.db.models.journal import JournalEntry
    from app.db.models.user import User


class Collection(UUIDMixin, TimestampMixin, Base):
    """User-created collection for grouping journal entries."""

    __tablename__ = "collections"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_pinned: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="collections")
    entries: Mapped[list[JournalEntry]] = relationship(
        "JournalEntry",
        secondary="collection_entries",
        back_populates="collections",
    )

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="collections_user_id_name_key"),
        CheckConstraint("name = lower(name)", name="collections_name_lower_check"),
        Index("idx_collections_user_id", "user_id"),
    )


class CollectionEntry(Base):
    """Junction model mapping a JournalEntry to a Collection with sequencing."""

    __tablename__ = "collection_entries"

    collection_id: Mapped[str] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE"),
        primary_key=True,
    )
    journal_entry_id: Mapped[str] = mapped_column(
        ForeignKey("journal_entries.id", ondelete="CASCADE"),
        primary_key=True,
    )
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (Index("idx_collection_entries_entry", "journal_entry_id"),)
