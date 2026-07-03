"""Search service.

Contains all business logic for the search feature.

Rules:
- No FastAPI imports (APIRouter, Request, Response, Depends, HTTPException).
- No direct SQLAlchemy access — use repositories only (or session helper methods).
- No imports from other feature modules (except schemas for response serialization).
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from sqlalchemy import Float, desc, func, select, type_coerce
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Day, EntryMood, JournalEntry
from app.db.models.ai import Embedding, JournalChunk
from app.modules.journal.schemas import JournalEntryResponse
from app.modules.search.schemas import SearchResultItem
from app.services.embeddings import get_embedding_generator


class SearchService:
    """Service class encapsulating the search business logic."""

    @staticmethod
    async def search_entries(
        db: AsyncSession,
        user_id: UUID,
        query: str,
        mode: Literal["instant", "semantic", "hybrid"] = "hybrid",
        limit: int = 20,
    ) -> list[SearchResultItem]:
        """Perform search over journal entries based on the requested mode.

        Args:
            db: Database session.
            user_id: The UUID of the searching user.
            query: The search query string.
            mode: The search mode ("instant", "semantic", "hybrid").
            limit: The maximum number of results to return.

        Returns:
            A list of SearchResultItem schemas.
        """
        # Trim query and return early if empty
        cleaned_query = query.strip() if query else ""
        if not cleaned_query:
            return []

        if mode == "instant":
            return await SearchService._instant_search(
                db, user_id, cleaned_query, limit
            )
        elif mode == "semantic":
            return await SearchService._semantic_search(
                db, user_id, cleaned_query, limit
            )
        else:
            return await SearchService._hybrid_search(db, user_id, cleaned_query, limit)

    @staticmethod
    async def _instant_search(
        db: AsyncSession, user_id: UUID, query: str, limit: int
    ) -> list[SearchResultItem]:
        """Full-Text Search (Lexical-only) strategy."""
        ts_query = func.websearch_to_tsquery("english", query)

        # 1. Fetch matching entry IDs and ranks
        stmt = (
            select(
                JournalEntry.id,
                func.ts_rank(JournalEntry.search_vector, ts_query).label("rank"),
            )
            .join(Day, JournalEntry.day_id == Day.id)
            .where(
                Day.user_id == user_id,
                JournalEntry.deleted_at.is_(None),
                JournalEntry.search_vector.op("@@")(ts_query),
            )
            .order_by(desc("rank"))
            .limit(limit)
        )
        res = await db.execute(stmt)
        rows = res.all()
        if not rows:
            return []

        entry_ids = [UUID(str(row[0])) for row in rows]
        ranks_map = {UUID(str(row[0])): float(row[1]) for row in rows}

        # 2. Fetch full entry details eager-loading relationships
        entries = await SearchService._fetch_entries_by_ids(db, user_id, entry_ids)
        entries_map = {entry.id: entry for entry in entries}

        # 3. Build response matching FTS rank order
        results = []
        for entry_id in entry_ids:
            entry = entries_map.get(entry_id)
            if entry:
                results.append(
                    SearchResultItem(
                        entry=JournalEntryResponse.model_validate(entry),
                        score=ranks_map[entry_id],
                        match_type="keyword",
                        highlight_snippet=None,
                    )
                )
        return results

    @staticmethod
    async def _semantic_search(
        db: AsyncSession, user_id: UUID, query: str, limit: int
    ) -> list[SearchResultItem]:
        """Vector similarity search (Semantic-only) strategy."""
        # 1. Generate query embedding vector using singleton
        generator = get_embedding_generator()
        query_vector = await generator.generate(query)

        # 2. Find closest chunk for each journal entry
        subq = (
            select(
                JournalChunk.journal_entry_id,
                JournalChunk.content,
                type_coerce(Embedding.embedding.op("<=>")(query_vector), Float).label(
                    "distance"
                ),
                func.row_number()
                .over(
                    partition_by=JournalChunk.journal_entry_id,
                    order_by=Embedding.embedding.op("<=>")(query_vector).asc(),
                )
                .label("rn"),
            )
            .select_from(Embedding)
            .join(JournalChunk, Embedding.chunk_id == JournalChunk.id)
            .where(Embedding.user_id == user_id)
            .subquery()
        )

        stmt = (
            select(subq.c.journal_entry_id, subq.c.content, subq.c.distance)
            .where(subq.c.rn == 1)
            .order_by(subq.c.distance.asc())
            .limit(limit)
        )
        res = await db.execute(stmt)
        rows = res.all()
        if not rows:
            return []

        entry_ids = [UUID(str(row[0])) for row in rows]
        distance_map = {UUID(str(row[0])): float(row[2]) for row in rows}
        content_map = {UUID(str(row[0])): row[1] for row in rows}

        # 3. Fetch full entry details eager-loading relationships
        entries = await SearchService._fetch_entries_by_ids(db, user_id, entry_ids)
        entries_map = {entry.id: entry for entry in entries}

        # 4. Build response matching distance order
        results = []
        for entry_id in entry_ids:
            entry = entries_map.get(entry_id)
            if entry:
                # Cosine similarity is usually defined as 1 - cosine_distance
                score = 1.0 - distance_map[entry_id]
                results.append(
                    SearchResultItem(
                        entry=JournalEntryResponse.model_validate(entry),
                        score=score,
                        match_type="semantic",
                        highlight_snippet=content_map[entry_id],
                    )
                )
        return results

    @staticmethod
    async def _hybrid_search(
        db: AsyncSession, user_id: UUID, query: str, limit: int
    ) -> list[SearchResultItem]:
        """Hybrid Search combining Full-Text and Vector ranks via Reciprocal Rank Fusion (RRF)."""
        # 1. Generate query embedding vector using singleton
        generator = get_embedding_generator()
        query_vector = await generator.generate(query)

        ts_query = func.websearch_to_tsquery("english", query)

        # 2. Build lexical ranking query
        lexical_cte = (
            select(
                JournalEntry.id,
                func.row_number()
                .over(
                    order_by=func.ts_rank(JournalEntry.search_vector, ts_query).desc()
                )
                .label("pos"),
            )
            .join(Day, JournalEntry.day_id == Day.id)
            .where(
                Day.user_id == user_id,
                JournalEntry.deleted_at.is_(None),
                JournalEntry.search_vector.op("@@")(ts_query),
            )
            .limit(100)
        ).cte("lexical_search")

        # 3. Build semantic ranking query
        semantic_subq = (
            select(
                JournalChunk.journal_entry_id,
                JournalChunk.content,
                type_coerce(Embedding.embedding.op("<=>")(query_vector), Float).label(
                    "distance"
                ),
                func.row_number()
                .over(
                    partition_by=JournalChunk.journal_entry_id,
                    order_by=Embedding.embedding.op("<=>")(query_vector).asc(),
                )
                .label("rn"),
            )
            .select_from(Embedding)
            .join(JournalChunk, Embedding.chunk_id == JournalChunk.id)
            .where(Embedding.user_id == user_id)
            .subquery()
        )

        semantic_cte = (
            select(
                semantic_subq.c.journal_entry_id.label("id"),
                semantic_subq.c.content.label("content"),
                semantic_subq.c.distance.label("distance"),
                func.row_number()
                .over(order_by=semantic_subq.c.distance.asc())
                .label("pos"),
            )
            .where(semantic_subq.c.rn == 1)
            .limit(100)
        ).cte("semantic_search")

        # 4. Reciprocal Rank Fusion (RRF) Join
        rrf_score = (
            func.coalesce(1.0 / (60 + lexical_cte.c.pos), 0.0)
            + func.coalesce(1.0 / (60 + semantic_cte.c.pos), 0.0)
        ).label("rrf_score")

        stmt = (
            select(
                func.coalesce(lexical_cte.c.id, semantic_cte.c.id).label("entry_id"),
                semantic_cte.c.content.label("highlight_snippet"),
                rrf_score,
                # Track matching types
                lexical_cte.c.pos.label("lexical_pos"),
                semantic_cte.c.pos.label("semantic_pos"),
            )
            .select_from(
                lexical_cte.join(
                    semantic_cte,
                    lexical_cte.c.id == semantic_cte.c.id,
                    full=True,
                )
            )
            .order_by(desc("rrf_score"))
            .limit(limit)
        )
        res = await db.execute(stmt)
        rows = res.all()
        if not rows:
            return []

        entry_ids = [UUID(str(row[0])) for row in rows]
        content_map = {UUID(str(row[0])): row[1] for row in rows}
        score_map = {UUID(str(row[0])): float(row[2]) for row in rows}

        def get_match_type(
            lex_pos: int | None, sem_pos: int | None
        ) -> Literal["hybrid", "keyword", "semantic"]:
            if lex_pos is not None and sem_pos is not None:
                return "hybrid"
            elif lex_pos is not None:
                return "keyword"
            return "semantic"

        match_type_map: dict[UUID, Literal["hybrid", "keyword", "semantic"]] = {
            UUID(str(row[0])): get_match_type(row[3], row[4]) for row in rows
        }

        # 5. Fetch full entry details eager-loading relationships
        entries = await SearchService._fetch_entries_by_ids(db, user_id, entry_ids)
        entries_map = {entry.id: entry for entry in entries}

        # 6. Build response matching RRF order
        results = []
        for entry_id in entry_ids:
            entry = entries_map.get(entry_id)
            if entry:
                results.append(
                    SearchResultItem(
                        entry=JournalEntryResponse.model_validate(entry),
                        score=score_map[entry_id],
                        match_type=match_type_map[entry_id],
                        highlight_snippet=content_map[entry_id],
                    )
                )
        return results

    @staticmethod
    async def _fetch_entries_by_ids(
        db: AsyncSession, user_id: UUID, entry_ids: list[UUID]
    ) -> list[JournalEntry]:
        """Fetch all specified entries with tags and moods eager-loaded."""
        if not entry_ids:
            return []
        stmt = (
            select(JournalEntry)
            .join(Day, JournalEntry.day_id == Day.id)
            .options(
                selectinload(JournalEntry.tags),
                selectinload(JournalEntry.moods).joinedload(EntryMood.mood),
            )
            .where(
                JournalEntry.id.in_(entry_ids),
                Day.user_id == user_id,
                JournalEntry.deleted_at.is_(None),
            )
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())
