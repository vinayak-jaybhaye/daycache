"""Reflect feature domain database models."""

from __future__ import annotations

from datetime import date as date_type
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.db.models.journal import JournalEntry


class ReflectSession(UUIDMixin, TimestampMixin, Base):
    """Reflect journaling session.

    One session per user, forever.
    """

    __tablename__ = "reflect_sessions"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships
    messages: Mapped[list[ReflectMessage]] = relationship(
        "ReflectMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ReflectMessage.created_at.asc(), ReflectMessage.id.asc()",
    )

    __table_args__ = (
        UniqueConstraint("user_id", name="reflect_sessions_user_id_key"),
        Index("idx_reflect_sessions_user", "user_id"),
    )


class ReflectMessage(UUIDMixin, Base):
    """Individual interaction turn in a Reflect session."""

    __tablename__ = "reflect_messages"

    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("reflect_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    date: Mapped[date_type] = mapped_column(Date, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    session: Mapped[ReflectSession] = relationship(
        "ReflectSession", back_populates="messages"
    )

    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'assistant')", name="reflect_messages_role_check"
        ),
        Index("idx_reflect_messages_session_date", "session_id", "date", "created_at"),
        Index(
            "idx_reflect_messages_session_created",
            "session_id",
            func.desc("created_at"),
        ),
    )


class ReflectEntry(UUIDMixin, Base):
    """Junction mapping a ReflectSession to a JournalEntry on a specific date."""

    __tablename__ = "reflect_entries"

    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("reflect_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    journal_entry_id: Mapped[UUID] = mapped_column(
        ForeignKey("journal_entries.id", ondelete="CASCADE"),
        nullable=False,
    )
    date: Mapped[date_type] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    last_message_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("reflect_messages.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    session: Mapped[ReflectSession] = relationship("ReflectSession")
    journal_entry: Mapped[JournalEntry] = relationship("JournalEntry")
    last_message: Mapped[ReflectMessage | None] = relationship("ReflectMessage")

    __table_args__ = (
        UniqueConstraint("session_id", "date", name="reflect_entries_session_date_key"),
        Index("idx_reflect_entries_session_date", "session_id", "date"),
    )
