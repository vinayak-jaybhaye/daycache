"""ORM model registry for Alembic autogenerate.

Import every ORM model here so that ``Base.metadata`` is fully populated
when Alembic inspects it during ``alembic revision --autogenerate``.
"""

from __future__ import annotations

from app.db.base import Base
from app.db.models.ai import Embedding, JournalChunk, Summary
from app.db.models.auth import Device, OAuthAccount, Session
from app.db.models.collection import Collection, CollectionEntry
from app.db.models.journal import Day, JournalEntry
from app.db.models.media import JournalMedia, Media
from app.db.models.mood import EntryMood, Mood
from app.db.models.recall import RecallMessage, RecallSession
from app.db.models.tag import JournalTag, Tag
from app.db.models.user import User, UserSettings

__all__ = [
    "Base",
    "Collection",
    "CollectionEntry",
    "Day",
    "Device",
    "Embedding",
    "EntryMood",
    "JournalChunk",
    "JournalEntry",
    "JournalMedia",
    "JournalTag",
    "Media",
    "Mood",
    "OAuthAccount",
    "RecallMessage",
    "RecallSession",
    "Session",
    "Summary",
    "Tag",
    "User",
    "UserSettings",
]
