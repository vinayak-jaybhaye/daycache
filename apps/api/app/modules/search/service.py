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
from sqlalchemy.orm import joinedload, selectinload

from app.db.models import Day, EntryMood, JournalEntry
from app.db.models.ai import Embedding, JournalChunk
from app.modules.journal.schemas import JournalEntryResponse
from app.modules.search.schemas import SearchResultItem
from app.services.embeddings import get_embedding_generator


class SearchService:
    """Service class encapsulating the search business logic."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def search(
        self,
        query: str,
        user_id: UUID,
        mode: Literal["instant", "semantic", "hybrid"] = "hybrid",
        limit: int = 20,
        context: bool = False,
    ) -> list[SearchResultItem]:
        """Wrapper method for Recall to perform search queries using instance db session."""
        return await self.search_entries(
            db=self.db,
            user_id=user_id,
            query=query,
            mode=mode,
            limit=limit,
            context=context,
        )

    @staticmethod
    async def search_entries(
        db: AsyncSession,
        user_id: UUID,
        query: str,
        mode: Literal["instant", "semantic", "hybrid"] = "hybrid",
        limit: int = 20,
        skip: int = 0,
        context: bool = False,
    ) -> list[SearchResultItem]:
        """Perform search over journal entries based on the requested mode.

        Args:
            db: Database session.
            user_id: The UUID of the searching user.
            query: The search query string.
            mode: The search mode ("instant", "semantic", "hybrid").
            limit: The maximum number of results to return.
            skip: The number of results to skip (pagination).

        Returns:
            A list of SearchResultItem schemas.
        """
        # Trim query and return early if empty
        cleaned_query = query.strip() if query else ""
        if not cleaned_query:
            return []

        if mode == "instant":
            return await SearchService._instant_search(
                db, user_id, cleaned_query, limit, skip, context
            )
        elif mode == "semantic":
            return await SearchService._semantic_search(
                db, user_id, cleaned_query, limit, skip, context
            )
        else:
            return await SearchService._hybrid_search(
                db, user_id, cleaned_query, limit, skip, context
            )

    @staticmethod
    async def _instant_search(
        db: AsyncSession,
        user_id: UUID,
        query: str,
        limit: int,
        skip: int,
        context: bool = False,
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
            .order_by(desc("rank"), JournalEntry.id.asc())
            .offset(skip)
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
                        highlight_snippet=entry.content_text if context else None,
                        day_date=entry.day.date if entry.day else None,
                    )
                )
        return results

    @staticmethod
    async def _semantic_search(
        db: AsyncSession,
        user_id: UUID,
        query: str,
        limit: int,
        skip: int,
        context: bool = False,
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
            .order_by(subq.c.distance.asc(), subq.c.journal_entry_id.asc())
            .offset(skip)
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
                        highlight_snippet=entry.content_text
                        if context
                        else content_map.get(entry_id),
                        day_date=entry.day.date if entry.day else None,
                    )
                )
        return results

    @staticmethod
    async def _hybrid_search(
        db: AsyncSession,
        user_id: UUID,
        query: str,
        limit: int,
        skip: int,
        context: bool = False,
    ) -> list[SearchResultItem]:
        """Hybrid Search combining Full-Text and Vector ranks via Reciprocal Rank Fusion (RRF)."""
        # 1. Generate query embedding vector using singleton
        generator = get_embedding_generator()
        query_vector = await generator.generate(query)

        ts_query = func.websearch_to_tsquery("english", query)
        inner_limit = max(100, skip + limit)

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
            .limit(inner_limit)
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
            .limit(inner_limit)
        ).cte("semantic_search")

        # 4. Reciprocal Rank Fusion (RRF) Join
        rrf_score = (
            func.coalesce(1.0 / (60 + lexical_cte.c.pos), 0.0)
            + func.coalesce(1.0 / (60 + semantic_cte.c.pos), 0.0)
        ).label("rrf_score")

        entry_id_col = func.coalesce(lexical_cte.c.id, semantic_cte.c.id).label(
            "entry_id"
        )

        stmt = (
            select(
                entry_id_col,
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
            .order_by(desc("rrf_score"), entry_id_col.asc())
            .offset(skip)
            .limit(limit)
        )
        res = await db.execute(stmt)
        rows = res.all()
        if not rows:
            return []

        entry_ids = [UUID(str(row[0])) for row in rows]
        content_map = {UUID(str(row[0])): row[1] for row in rows}
        # Normalize hybrid RRF score so it falls between 0 and 1:
        # Max score is rank 1 on both lexical and semantic (1/61 + 1/61 = 2/61)
        max_rrf = 2.0 / 61.0
        score_map = {UUID(str(row[0])): float(row[2]) / max_rrf for row in rows}

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
                        highlight_snippet=entry.content_text
                        if context
                        else content_map.get(entry_id),
                        day_date=entry.day.date if entry.day else None,
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
                joinedload(JournalEntry.day),
                selectinload(JournalEntry.tags),
                selectinload(JournalEntry.moods).joinedload(EntryMood.mood),
                selectinload(JournalEntry.media),
            )
            .where(
                JournalEntry.id.in_(entry_ids),
                Day.user_id == user_id,
                JournalEntry.deleted_at.is_(None),
            )
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())
