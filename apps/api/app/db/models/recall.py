"""Recall feature domain database models."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class RecallSession(UUIDMixin, TimestampMixin, Base):
    """Memory retrieval session.

    One session per user, forever.
    """

    __tablename__ = "recall_sessions"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships
    messages: Mapped[list[RecallMessage]] = relationship(
        "RecallMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="RecallMessage.created_at.asc(), RecallMessage.id.asc()",
    )

    __table_args__ = (
        UniqueConstraint("user_id", name="recall_sessions_user_id_key"),
        Index("idx_recall_sessions_user", "user_id"),
    )


class RecallMessage(UUIDMixin, Base):
    """Individual interaction turn in a Recall session."""

    __tablename__ = "recall_messages"

    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("recall_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    retrieved_entries: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    session: Mapped[RecallSession] = relationship(
        "RecallSession", back_populates="messages"
    )

    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'assistant')", name="recall_messages_role_check"
        ),
        Index("idx_recall_messages_session", "session_id", "created_at"),
    )
