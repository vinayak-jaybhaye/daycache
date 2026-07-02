"""SQLAlchemy declarative base and shared model mixins."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Project-wide SQLAlchemy declarative base.

    All ORM models in ``db/models/`` must inherit from this class so that
    Alembic autogenerate can discover them via ``Base.metadata``.
    """


class TimestampMixin:
    """Adds ``created_at`` and ``updated_at`` columns to any model.

    Both columns are managed entirely by the database server,
    which avoids clock-skew issues in multi-instance deployments.

    Usage::

        class Entry(TimestampMixin, Base):
            __tablename__ = "entries"
            ...
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
