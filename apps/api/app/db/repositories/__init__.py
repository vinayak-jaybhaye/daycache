"""Public repository exports.

Add feature repository imports here as they are implemented:

    from app.db.repositories.auth import UserRepository      # noqa: F401
    from app.db.repositories.journal import EntryRepository  # noqa: F401
"""

from app.db.repositories.base import BaseRepository

__all__ = ["BaseRepository"]
