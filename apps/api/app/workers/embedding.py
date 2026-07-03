"""Embedding background tasks."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.embeddings.service import EmbeddingService

logger = logging.getLogger(__name__)


async def process_journal_entry_embeddings(
    ctx: dict[str, Any], entry_id: str, version: int
) -> None:
    """Worker task to run chunking and embeddings generation asynchronously."""
    db: AsyncSession = ctx["db"]
    logger.info(
        "Starting background embedding processing for entry %s, version %d",
        entry_id,
        version,
    )
    await EmbeddingService.process_entry_embeddings(db, UUID(entry_id), version)
