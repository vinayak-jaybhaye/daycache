"""Ai API router."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user, get_db
from app.db.enums import SummaryKind, SummaryScope
from app.db.models import User
from app.db.repositories.summary import SummaryRepository
from app.modules.ai.schemas import SummaryResponse

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get(
    "/entry/{entry_id}",
    response_model=SummaryResponse,
    status_code=status.HTTP_200_OK,
)
async def get_entry_summary(
    entry_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SummaryResponse:
    """Fetch the latest summary for a specific journal entry, generating it on-the-fly if missing or stale."""
    import hashlib

    from app.db.repositories.journal import JournalRepository
    from app.modules.ai.service import AISummaryService

    journal_repo = JournalRepository(db)
    entry = await journal_repo.get_entry_by_id(entry_id, current_user.id)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Journal entry {entry_id} not found",
        )

    entry_text = (entry.content_text or "").strip()
    if not entry_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Journal entry is empty. Cannot generate summary.",
        )

    # Populate hash on the fly for legacy database entries if missing
    if not entry.content_hash:
        entry.content_hash = hashlib.sha256(entry_text.encode("utf-8")).hexdigest()
        await db.flush()

    summary_repo = SummaryRepository(db)
    summary = await summary_repo.get_latest(
        user_id=current_user.id,
        scope=SummaryScope.ENTRY,
        kind=SummaryKind.SUMMARY,
        journal_entry_id=entry_id,
    )

    if not summary or summary.content_hash != entry.content_hash:
        generated = await AISummaryService.generate_summary(
            db,
            user_id=current_user.id,
            scope=SummaryScope.ENTRY,
            journal_entry_id=entry_id,
        )
        if generated:
            await db.flush()
            summary = generated

    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No summary found for entry {entry_id}",
        )
    return SummaryResponse.model_validate(summary)


@router.get(
    "/day/{date_val}",
    response_model=SummaryResponse,
    status_code=status.HTTP_200_OK,
)
async def get_day_summary(
    date_val: date,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SummaryResponse:
    """Fetch the latest daily summary for a specific calendar date, generating it on-the-fly if missing or stale."""
    import hashlib

    from sqlalchemy import select

    from app.db.models.journal import JournalEntry
    from app.db.repositories.journal import DayRepository
    from app.modules.ai.service import AISummaryService

    day_repo = DayRepository(db)
    day = await day_repo.get_by_date(current_user.id, date_val)
    if not day:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No day entry found for date {date_val}",
        )

    # Fetch all non-deleted entries for this day to compute the current hash
    stmt = (
        select(JournalEntry)
        .where(
            JournalEntry.day_id == day.id,
            JournalEntry.deleted_at.is_(None),
        )
        .order_by(JournalEntry.created_at.asc(), JournalEntry.id.asc())
    )
    res = await db.execute(stmt)
    entries = res.scalars().all()

    # Filter entries that actually have some content text
    valid_entries = [e for e in entries if (e.content_text or "").strip()]

    if not valid_entries:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"No text content found in journal entries for date {date_val}.",
        )

    # Populate hash on the fly for legacy database entries if missing
    hashes_modified = False
    for e in valid_entries:
        if not e.content_hash:
            e_text = (e.content_text or "").strip()
            e.content_hash = hashlib.sha256(e_text.encode("utf-8")).hexdigest()
            hashes_modified = True
    if hashes_modified:
        await db.flush()

    # Combine entry hashes to create a deterministic daily content signature
    combined_hashes_text = "".join(
        e.content_hash for e in valid_entries if e.content_hash
    )
    day_hash = hashlib.sha256(combined_hashes_text.encode("utf-8")).hexdigest()

    summary_repo = SummaryRepository(db)
    summary = await summary_repo.get_latest(
        user_id=current_user.id,
        scope=SummaryScope.DAY,
        kind=SummaryKind.SUMMARY,
        day_id=day.id,
    )

    if not summary or summary.content_hash != day_hash:
        generated = await AISummaryService.generate_summary(
            db,
            user_id=current_user.id,
            scope=SummaryScope.DAY,
            day_id=day.id,
            period_start=day.date,
            period_end=day.date,
        )
        if generated:
            await db.flush()
            summary = generated

    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No summary found for date {date_val}",
        )
    return SummaryResponse.model_validate(summary)


@router.get(
    "/week/{target_date}",
    response_model=SummaryResponse,
    status_code=status.HTTP_200_OK,
)
async def get_week_summary(
    target_date: date,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SummaryResponse:
    """Fetch the latest weekly summary for the ISO week containing the given target_date, generating it on-the-fly if missing or stale."""
    from app.modules.ai.service import AISummaryService, get_week_bounds

    # Align input to deterministic ISO week bounds (Monday to Sunday)
    week_start, week_end = get_week_bounds(target_date)
    has_entries = await AISummaryService.has_entries_in_range(
        db, current_user.id, week_start, week_end
    )
    if not has_entries:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"No journal entries found in week {week_start} - {week_end}.",
        )

    summary = await AISummaryService.generate_summary(
        db,
        user_id=current_user.id,
        scope=SummaryScope.WEEK,
        period_start=week_start,
        period_end=week_end,
    )

    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No weekly summary found starting on {week_start}",
        )
    return SummaryResponse.model_validate(summary)


@router.get(
    "/month/{year}/{month}",
    response_model=SummaryResponse,
    status_code=status.HTTP_200_OK,
)
async def get_month_summary(
    year: int,
    month: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SummaryResponse:
    """Fetch the latest monthly summary for the given year and month, generating it on-the-fly if missing or stale."""
    import calendar

    from app.modules.ai.service import AISummaryService

    try:
        month_start = date(year, month, 1)
        _, last_day = calendar.monthrange(year, month)
        month_end = date(year, month, last_day)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid year/month combination: {e}",
        ) from e

    has_entries = await AISummaryService.has_entries_in_range(
        db, current_user.id, month_start, month_end
    )
    if not has_entries:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"No journal entries found for month {year}-{month:02d}.",
        )

    summary = await AISummaryService.generate_summary(
        db,
        user_id=current_user.id,
        scope=SummaryScope.MONTH,
        period_start=month_start,
        period_end=month_end,
    )

    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No monthly summary found for {year}-{month:02d}",
        )
    return SummaryResponse.model_validate(summary)


@router.get(
    "/year/{year}",
    response_model=SummaryResponse,
    status_code=status.HTTP_200_OK,
)
async def get_year_summary(
    year: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SummaryResponse:
    """Fetch the latest yearly summary for the given year, generating it on-the-fly only if the year is not current."""
    from app.modules.ai.service import AISummaryService

    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)

    has_entries = await AISummaryService.has_entries_in_range(
        db, current_user.id, year_start, year_end
    )
    if not has_entries:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"No journal entries found in year {year}.",
        )

    # If the requested year is the ongoing/current year, do not generate on-the-fly
    if year == date.today().year:
        summary_repo = SummaryRepository(db)
        summary = await summary_repo.get_latest(
            user_id=current_user.id,
            scope=SummaryScope.YEAR,
            kind=SummaryKind.SUMMARY,
            period_start=year_start,
        )
        if not summary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"The year {year} is still ongoing! Yearly summaries are compiled at the end of the year. Keep journaling to build your story!",
            )
    else:
        # Generate/fetch on-the-fly for past years
        summary = await AISummaryService.generate_summary(
            db,
            user_id=current_user.id,
            scope=SummaryScope.YEAR,
            period_start=year_start,
            period_end=year_end,
        )

    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No yearly summary found for {year}.",
        )
    return SummaryResponse.model_validate(summary)
