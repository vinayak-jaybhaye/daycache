"""SQLAlchemy declarative base and shared model mixins."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Project-wide SQLAlchemy declarative base.

    All ORM models in ``db/models/`` must inherit from this class so that
    Alembic autogenerate can discover them via ``Base.metadata``.
    """


class UUIDMixin:
    """Adds a UUID primary key ``id`` to any model.

    Standardised UUID primary keys with database-generated UUIDs.
    """

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )


class TimestampMixin:
    """Adds ``created_at`` and ``updated_at`` columns to any model.

    Both columns are managed entirely by the database server,
    which avoids clock-skew issues in multi-instance deployments.
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


class SoftDeleteMixin:
    """Adds a ``deleted_at`` column for soft-delete support.

    Required for tables holding user-generated content.
    """

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )
