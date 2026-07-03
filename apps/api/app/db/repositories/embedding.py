"""Embedding database repository."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import delete

from app.db.models.ai import Embedding, JournalChunk
from app.db.repositories.base import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class EmbeddingRepository(BaseRepository[JournalChunk]):
    """Repository handling database operations for JournalChunk and Embedding models."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, JournalChunk)

    async def clear_chunks(self, journal_entry_id: UUID) -> None:
        """Delete all chunks for a journal entry (cascades database-level delete to embeddings)."""
        stmt = delete(JournalChunk).where(
            JournalChunk.journal_entry_id == journal_entry_id
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def save_chunks_and_embeddings(
        self, chunks: list[JournalChunk], embeddings: list[Embedding]
    ) -> None:
        """Bulk save chunks and embeddings to the database."""
        self._session.add_all(chunks)
        await self._session.flush()

        self._session.add_all(embeddings)
        await self._session.flush()
