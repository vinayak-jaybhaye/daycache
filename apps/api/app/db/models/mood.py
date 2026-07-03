"""Mood and EntryMood domain models."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    SmallInteger,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDMixin

if TYPE_CHECKING:
    from app.db.models.journal import JournalEntry


class Mood(UUIDMixin, Base):
    """System-defined mood categories (e.g. happy, sad, neutral)."""

    __tablename__ = "moods"

    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    color: Mapped[str] = mapped_column(Text, nullable=False)


class EntryMood(UUIDMixin, Base):
    """Mood mapping associated with a specific JournalEntry with intensity score."""

    __tablename__ = "entry_moods"

    journal_entry_id: Mapped[str] = mapped_column(
        ForeignKey("journal_entries.id", ondelete="CASCADE"),
        nullable=False,
    )
    mood_id: Mapped[str] = mapped_column(
        ForeignKey("moods.id", ondelete="CASCADE"),
        nullable=False,
    )
    intensity: Mapped[int] = mapped_column(
        SmallInteger,
        default=5,
        nullable=False,
    )

    # Relationships
    journal_entry: Mapped[JournalEntry] = relationship(
        "JournalEntry", back_populates="moods"
    )
    mood: Mapped[Mood] = relationship("Mood")

    __table_args__ = (
        UniqueConstraint(
            "journal_entry_id",
            "mood_id",
            name="entry_moods_journal_entry_id_mood_id_key",
        ),
        CheckConstraint(
            "intensity BETWEEN 1 AND 10",
            name="entry_moods_intensity_check",
        ),
        Index("idx_entry_moods_entry", "journal_entry_id"),
    )
