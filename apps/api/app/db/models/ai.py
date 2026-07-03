"""AI (Chunking, Embeddings, Summaries) domain models."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDMixin
from app.db.enums import SummaryKind, SummaryScope

if TYPE_CHECKING:
    from app.db.models.journal import Day, JournalEntry
    from app.db.models.user import User


class JournalChunk(UUIDMixin, Base):
    """Segmented text chunk from a JournalEntry for semantic search parsing."""

    __tablename__ = "journal_chunks"

    journal_entry_id: Mapped[str] = mapped_column(
        ForeignKey("journal_entries.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    character_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    journal_entry: Mapped[JournalEntry] = relationship(
        "JournalEntry", back_populates="chunks"
    )
    embeddings: Mapped[list[Embedding]] = relationship(
        "Embedding",
        back_populates="chunk",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "journal_entry_id",
            "chunk_index",
            name="journal_chunks_journal_entry_id_chunk_index_key",
        ),
        Index("idx_chunks_entry_id", "journal_entry_id"),
        Index("idx_chunks_hash", "journal_entry_id", "content_hash"),
    )


class Embedding(UUIDMixin, Base):
    """Vector embedding of a specific JournalChunk."""

    __tablename__ = "embeddings"

    chunk_id: Mapped[str] = mapped_column(
        ForeignKey("journal_chunks.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Any] = mapped_column(Vector(768), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    chunk: Mapped[JournalChunk] = relationship(
        "JournalChunk", back_populates="embeddings"
    )
    user: Mapped[User] = relationship("User", back_populates="embeddings")

    __table_args__ = (
        UniqueConstraint("chunk_id", "model", name="embeddings_chunk_id_model_key"),
        Index("idx_embeddings_user_id", "user_id"),
        Index("idx_embeddings_chunk_id", "chunk_id"),
        Index(
            "idx_embeddings_vector",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_with={"lists": 100},
        ),
    )


class Summary(UUIDMixin, Base):
    """AI-generated summary of journal entries over a given scope (entry, day, week, etc.)."""

    __tablename__ = "summaries"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    scope: Mapped[SummaryScope] = mapped_column(
        SQLEnum("entry", "day", "week", "month", "year", name="summary_scope"),
        nullable=False,
    )
    kind: Mapped[SummaryKind] = mapped_column(
        SQLEnum("summary", name="summary_kind"),
        default=SummaryKind.SUMMARY,
        nullable=False,
    )

    journal_entry_id: Mapped[str | None] = mapped_column(
        ForeignKey("journal_entries.id", ondelete="CASCADE"),
        nullable=True,
    )
    day_id: Mapped[str | None] = mapped_column(
        ForeignKey("days.id", ondelete="CASCADE"),
        nullable=True,
    )
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)

    content: Mapped[str] = mapped_column(Text, nullable=False)
    highlights: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    challenges: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    themes: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    mood_analysis: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    provider: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[str] = mapped_column(Text, default="v1", nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="summaries")
    journal_entry: Mapped[JournalEntry | None] = relationship(
        "JournalEntry", back_populates="summaries"
    )
    day: Mapped[Day | None] = relationship("Day", back_populates="summaries")

    __table_args__ = (
        CheckConstraint(
            "(scope = 'entry' AND journal_entry_id IS NOT NULL AND day_id IS NULL AND period_start IS NULL) OR "
            "(scope = 'day' AND day_id IS NOT NULL AND journal_entry_id IS NULL AND period_start IS NULL) OR "
            "(scope IN ('week', 'month', 'year') AND period_start IS NOT NULL AND period_end IS NOT NULL AND journal_entry_id IS NULL AND day_id IS NULL)",
            name="valid_summary_reference",
        ),
        Index(
            "idx_summaries_user", "user_id", "scope", "kind", text("created_at DESC")
        ),
        Index(
            "idx_summaries_entry",
            "journal_entry_id",
            "kind",
            text("created_at DESC"),
            postgresql_where=text("journal_entry_id IS NOT NULL"),
        ),
        Index(
            "idx_summaries_day",
            "day_id",
            "kind",
            text("created_at DESC"),
            postgresql_where=text("day_id IS NOT NULL"),
        ),
        Index(
            "idx_summaries_period",
            "user_id",
            "scope",
            "period_start",
            text("created_at DESC"),
            postgresql_where=text("period_start IS NOT NULL"),
        ),
    )
