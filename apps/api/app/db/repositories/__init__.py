"""Public repository exports.

Provides base and concrete domain repositories.
"""

from __future__ import annotations

from app.db.repositories.base import BaseRepository
from app.db.repositories.collection import CollectionRepository
from app.db.repositories.collection_entry import CollectionEntryRepository
from app.db.repositories.device import DeviceRepository
from app.db.repositories.embedding import EmbeddingRepository
from app.db.repositories.entry_mood import EntryMoodRepository
from app.db.repositories.journal import DayRepository, JournalRepository
from app.db.repositories.journal_tag import JournalTagRepository
from app.db.repositories.media import MediaRepository
from app.db.repositories.mood import MoodRepository
from app.db.repositories.session import SessionRepository
from app.db.repositories.settings import SettingsRepository
from app.db.repositories.summary import SummaryRepository
from app.db.repositories.tag import TagRepository
from app.db.repositories.user import UserRepository

__all__ = [
    "BaseRepository",
    "CollectionEntryRepository",
    "CollectionRepository",
    "DayRepository",
    "DeviceRepository",
    "EmbeddingRepository",
    "EntryMoodRepository",
    "JournalRepository",
    "JournalTagRepository",
    "MediaRepository",
    "MoodRepository",
    "SessionRepository",
    "SettingsRepository",
    "SummaryRepository",
    "TagRepository",
    "UserRepository",
]
