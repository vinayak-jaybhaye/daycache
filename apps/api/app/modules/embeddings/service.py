"""Embedding service.

Contains all business logic for text chunking and vector embedding generation.

Rules:
- No FastAPI imports (APIRouter, Request, Response, Depends, HTTPException).
- No direct SQLAlchemy access — use repositories only.
- No imports from other feature modules.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

from app.db.enums import EmbeddingStatus
from app.db.models.ai import Embedding, JournalChunk
from app.db.repositories.embedding import EmbeddingRepository
from app.db.repositories.journal import JournalRepository
from app.services.embeddings import EmbeddingGenerator

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Orchestrates text chunking, embedding generation, and status updates."""

    @staticmethod
    def build_chunk_for_embedding(
        chunk_text: str,
        date_val: date,
        title: str | None,
        tags: list[str] | None = None,
        moods: list[str] | None = None,
    ) -> str:
        """Prepend a lightweight header to the chunk to anchor it temporally and semantically for embedding generation."""
        header = f"[{date_val.strftime('%B %d, %Y')}]"
        if title:
            header += f" {title}"
        if tags:
            header += f" | Tags: {', '.join(tags)}"
        if moods:
            header += f" | Moods: {', '.join(moods)}"
        return f"{header}\n{chunk_text}"

    @staticmethod
    def chunk_text(text: str, max_chars: int = 1000, overlap: int = 100) -> list[str]:
        """Split text into overlapping character windows."""
        text = text.strip()
        if not text:
            return []
        if len(text) <= max_chars:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = start + max_chars
            chunk = text[start:end]
            chunks.append(chunk)
            start += max_chars - overlap
            if start >= len(text) - overlap:
                break
        return chunks

    @staticmethod
    async def process_entry_embeddings(
        db: AsyncSession, entry_id: UUID, version: int
    ) -> None:
        """Slices the entry text, generates embeddings, and commits them atomically.

        If the entry has been updated since enqueuing (version mismatch), aborts.
        """
        journal_repo = JournalRepository(db)
        embedding_repo = EmbeddingRepository(db)

        # 1. Fetch entry with Day eager loaded
        entry = await journal_repo.get_entry_for_ai(entry_id)
        if entry is None:
            logger.warning(
                "Journal entry %s not found for embedding processing", entry_id
            )
            return

        # 2. Guard: version mismatch
        if entry.version != version:
            logger.info(
                "Stale embedding job for entry %s. Current version: %d, job version: %d. Aborting.",
                entry_id,
                entry.version,
                version,
            )
            return

        # 3. Transition status to PROCESSING
        entry.embedding_status = EmbeddingStatus.PROCESSING
        await db.flush()
        await db.commit()

        try:
            # 4. Clear/prune chunks if empty text
            text_content = (entry.content_text or "").strip()
            if not text_content:
                await embedding_repo.clear_chunks(entry_id)

                # Fetch fresh reference in current transaction
                entry = await journal_repo.get_entry_for_ai(entry_id)
                if entry and entry.version == version:
                    entry.embedding_status = EmbeddingStatus.COMPLETED
                await db.commit()
                return

            # 5. Chunk text in memory
            chunks = EmbeddingService.chunk_text(text_content)

            # 6. Embed chunks in memory using the common interface
            tags_list = [t.name for t in entry.tags] if entry.tags else None
            moods_list = (
                [f"{m.mood.name} (intensity: {m.intensity})" for m in entry.moods]
                if entry.moods
                else None
            )

            prefixed_chunks = [
                EmbeddingService.build_chunk_for_embedding(
                    chunk_text=c,
                    date_val=entry.day.date,
                    title=entry.title,
                    tags=tags_list,
                    moods=moods_list,
                )
                for c in chunks
            ]

            generator = EmbeddingGenerator()
            embeddings = await generator.generate_batch(prefixed_chunks)

            # 7. Write to DB in a single atomic transaction
            # Clear old chunks first (this cascades to embeddings)
            await embedding_repo.clear_chunks(entry_id)

            # Create new JournalChunk and Embedding entities
            db_chunks = []
            db_embeddings = []

            for idx, chunk_text in enumerate(chunks):
                h = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
                char_count = len(chunk_text)
                # Character count divided by 4 as a simple token count estimate
                tok_count = max(1, len(chunk_text) // 4)

                db_chunk = JournalChunk(
                    journal_entry_id=str(entry_id),
                    chunk_index=idx,
                    content=chunk_text,
                    content_hash=h,
                    token_count=tok_count,
                    character_count=char_count,
                )
                db_chunks.append(db_chunk)

                # Linking via relationship
                db_embedding = Embedding(
                    chunk=db_chunk,
                    user_id=str(entry.day.user_id),
                    provider=generator.provider_name,
                    model=generator.model_name,
                    embedding=embeddings[idx],
                )
                db_embeddings.append(db_embedding)

            # Save them
            await embedding_repo.save_chunks_and_embeddings(db_chunks, db_embeddings)

            # Set status to COMPLETED
            entry = await journal_repo.get_entry_for_ai(entry_id)
            if entry and entry.version == version + 1:
                entry.embedding_status = EmbeddingStatus.COMPLETED

            await db.commit()
            logger.info(
                "Embedding processing completed successfully for entry %s", entry_id
            )

        except Exception as exc:
            logger.exception(
                "Embedding processing failed for entry %s: %s", entry_id, exc
            )
            await db.rollback()

            # Set status to FAILED in a fresh transaction
            try:
                entry = await journal_repo.get_entry_for_ai(entry_id)
                if entry and entry.version == version + 1:
                    entry.embedding_status = EmbeddingStatus.FAILED
                    await db.commit()
            except Exception as inner_exc:
                logger.error(
                    "Failed to mark entry %s status as FAILED: %s",
                    entry_id,
                    inner_exc,
                )

            raise exc
