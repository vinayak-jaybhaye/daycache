"""Generic typed base repository.

All feature repositories inherit from ``BaseRepository[ModelT]``.

Rules:
- Repositories are the **only** layer that may access SQLAlchemy directly.
- Business logic must never live inside a repository.
- Repositories must never import from ``app.modules``.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Generic async repository providing basic CRUD operations.

    Feature repositories extend this class and add query methods
    specific to their domain model.

    Args:
        session: The active ``AsyncSession`` for the current request.
        model: The SQLAlchemy ORM model class this repository manages.

    Example::

        class UserRepository(BaseRepository[User]):
            def __init__(self, session: AsyncSession) -> None:
                super().__init__(session, User)

            async def get_by_email(self, email: str) -> User | None:
                result = await self._session.execute(
                    select(User).where(User.email == email)
                )
                return result.scalar_one_or_none()
    """

    def __init__(self, session: AsyncSession, model: type[ModelT]) -> None:
        self._session = session
        self._model = model

    async def get_by_id(self, id: UUID) -> ModelT | None:
        """Fetch a single record by primary key.

        Args:
            id: The UUID primary key of the record.

        Returns:
            The model instance, or ``None`` if not found.
        """
        result = await self._session.execute(
            select(self._model).where(self._model.id == id)  # type: ignore[attr-defined]
        )
        return result.scalar_one_or_none()

    async def create(self, obj: ModelT) -> ModelT:
        """Persist a new model instance.

        The session is flushed so the database assigns auto-generated
        values (e.g. server-side ``created_at``) before returning.

        Args:
            obj: The unsaved model instance to persist.

        Returns:
            The same instance, now associated with the session.
        """
        self._session.add(obj)
        await self._session.flush()
        await self._session.refresh(obj)
        return obj

    async def delete(self, obj: ModelT) -> None:
        """Delete a model instance from the database.

        Args:
            obj: The model instance to delete. Must be associated with
                 the current session.
        """
        await self._session.delete(obj)
        await self._session.flush()

    async def _execute(self, stmt: Any) -> Any:
        """Execute an arbitrary SQLAlchemy statement.

        Exposed to subclasses as a convenience wrapper. Should not be
        called from outside the repository layer.
        """
        return await self._session.execute(stmt)
