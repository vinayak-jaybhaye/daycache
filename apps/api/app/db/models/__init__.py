"""ORM model registry for Alembic autogenerate.

Import every ORM model here so that ``Base.metadata`` is fully populated
when Alembic inspects it during ``alembic revision --autogenerate``.

Example (once models exist)::

    from app.db.models.user import User          # noqa: F401
    from app.db.models.session import Session    # noqa: F401
    from app.db.models.entry import Entry        # noqa: F401
"""

from app.db.base import Base

__all__ = ["Base"]
