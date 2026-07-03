"""Journal API routers for Entries and Days."""

from __future__ import annotations

import contextlib
from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_arq_pool, get_current_user, get_db
from app.db.models import User
from app.modules.journal.schemas import (
    DayResponse,
    DayUpdate,
    JournalEntryCreate,
    JournalEntryResponse,
    JournalEntryUpdate,
    LinkMoodRequest,
    LinkTagRequest,
    MoodResponse,
    PaginatedJournalEntriesResponse,
)
from app.modules.journal.service import JournalService

if TYPE_CHECKING:
    from arq import ArqRedis
    from sqlalchemy.ext.asyncio import AsyncSession

entries_router = APIRouter()
days_router = APIRouter()
moods_router = APIRouter()


# ==========================================
# Journal Entries Router Endpoints
# ==========================================


@entries_router.post(
    "",
    response_model=JournalEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_entry(
    data: JournalEntryCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis = Depends(get_arq_pool),
) -> JournalEntryResponse:
    """Create a new journal entry under the resolved Day aggregate."""
    entry = await JournalService.create_entry(db, current_user.id, data)
    with contextlib.suppress(Exception):
        await arq_pool.enqueue_job(
            "process_journal_entry_embeddings",
            str(entry.id),
            entry.version,
            _queue_name="embedding_queue",
        )
    return entry


@entries_router.get(
    "",
    response_model=PaginatedJournalEntriesResponse,
)
async def list_entries(
    limit: int = Query(20, ge=1, le=100, description="Items limit"),
    cursor: str | None = Query(None, description="Keyset base64 pagination cursor"),
    collection_id: UUID | None = Query(None, description="Filter by collection ID"),
    tag_id: UUID | None = Query(None, description="Filter by tag ID"),
    date: date | None = Query(None, description="Filter by calendar date"),
    is_favorite: bool | None = Query(None, description="Filter by favorite status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedJournalEntriesResponse:
    """Retrieve all journal entries matching the filters with pagination."""
    return await JournalService.list_entries(
        db=db,
        user_id=current_user.id,
        limit=limit,
        cursor=cursor,
        collection_id=collection_id,
        tag_id=tag_id,
        target_date=date,
        is_favorite=is_favorite,
    )


@entries_router.get(
    "/{id}",
    response_model=JournalEntryResponse,
)
async def get_entry(
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JournalEntryResponse:
    """Retrieve details of a specific journal entry by ID."""
    return await JournalService.get_entry(db, current_user.id, id)


@entries_router.patch(
    "/{id}",
    response_model=JournalEntryResponse,
)
async def update_entry(
    id: UUID,
    data: JournalEntryUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis = Depends(get_arq_pool),
) -> JournalEntryResponse:
    """Update metadata or rich text content of a journal entry with optimistic locking check."""
    entry = await JournalService.update_entry(db, current_user.id, id, data)

    # Trigger background embedding processing if title or content text is updated
    if data.title is not None or data.content is not None:
        with contextlib.suppress(Exception):
            await arq_pool.enqueue_job(
                "process_journal_entry_embeddings",
                str(entry.id),
                entry.version,
                _queue_name="embedding_queue",
            )

    return entry


@entries_router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_entry(
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft delete a journal entry by ID."""
    await JournalService.delete_entry(db, current_user.id, id)


@entries_router.post(
    "/{id}/tags",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def add_tag_to_entry(
    id: UUID,
    data: LinkTagRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Associate a tag with a journal entry."""
    await JournalService.add_tag_to_entry(
        db=db,
        user_id=current_user.id,
        entry_id=id,
        tag_id=data.tag_id,
    )


@entries_router.delete(
    "/{id}/tags/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_tag_from_entry(
    id: UUID,
    tag_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Dissociate a tag from a journal entry."""
    await JournalService.remove_tag_from_entry(
        db=db,
        user_id=current_user.id,
        entry_id=id,
        tag_id=tag_id,
    )


# ==========================================
# Days (Daily Context) Router Endpoints
# ==========================================


@days_router.get(
    "",
    response_model=list[DayResponse],
)
async def list_days(
    start_date: date = Query(..., description="Start date of filter range"),
    end_date: date = Query(..., description="End date of filter range"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DayResponse]:
    """Retrieve Day metadata records for calendar grid views."""
    return await JournalService.list_days(db, current_user.id, start_date, end_date)


@days_router.get(
    "/{date}",
    response_model=DayResponse,
)
async def get_day(
    date: date,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DayResponse:
    """Retrieve or create Day metadata aggregate for a calendar date."""
    return await JournalService.get_day_by_date(db, current_user.id, date)


@days_router.patch(
    "/{date}",
    response_model=DayResponse,
)
async def update_day(
    date: date,
    data: DayUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DayResponse:
    """Update location or weather metadata context for a calendar date."""
    return await JournalService.update_day(db, current_user.id, date, data)


# ==========================================
# Mood Catalog Router Endpoints
# ==========================================


@moods_router.get(
    "",
    response_model=list[MoodResponse],
)
async def list_moods(
    db: AsyncSession = Depends(get_db),
) -> list[MoodResponse]:
    """Retrieve the full predefined mood catalog ordered by name."""
    return await JournalService.list_moods(db)


# ==========================================
# Entry ↔ Mood Sub-resource Endpoints
# ==========================================


@entries_router.post(
    "/{id}/moods",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def add_mood_to_entry(
    id: UUID,
    data: LinkMoodRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Associate a mood with a journal entry."""
    await JournalService.add_mood_to_entry(
        db=db,
        user_id=current_user.id,
        entry_id=id,
        mood_id=data.mood_id,
        intensity=data.intensity,
    )


@entries_router.delete(
    "/{id}/moods/{mood_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_mood_from_entry(
    id: UUID,
    mood_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Dissociate a mood from a journal entry."""
    await JournalService.remove_mood_from_entry(
        db=db,
        user_id=current_user.id,
        entry_id=id,
        mood_id=mood_id,
    )
