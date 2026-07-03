from __future__ import annotations

import base64
from datetime import date as date_type
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy.orm.exc import StaleDataError

from app.db.models.journal import Day, JournalEntry
from app.db.repositories.journal import DayRepository, JournalRepository
from app.db.repositories.tag import TagRepository
from app.exceptions import ConflictError, NotFoundError, UnprocessableError
from app.modules.journal.schemas import (
    DayResponse,
    EntryMoodResponse,
    JournalEntryResponse,
    MoodResponse,
    PaginatedJournalEntriesResponse,
)
from app.modules.tags.schemas import TagInfo

if TYPE_CHECKING:
    from datetime import date

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.journal.schemas import (
        DayUpdate,
        JournalEntryCreate,
        JournalEntryUpdate,
    )


def encode_cursor(target_date: date_type, created_at: datetime, entry_id: UUID) -> str:
    """Encodes keyset attributes into a URL-safe Base64 string cursor."""
    cursor_str = f"{target_date.isoformat()}|{created_at.isoformat()}|{entry_id!s}"
    return base64.urlsafe_b64encode(cursor_str.encode("utf-8")).decode("utf-8")


def decode_cursor(cursor: str) -> tuple[date_type, datetime, UUID]:
    """Decodes a Base64 keyset cursor string back to date, datetime, and UUID."""
    try:
        decoded_bytes = base64.urlsafe_b64decode(cursor.encode("utf-8"))
        parts = decoded_bytes.decode("utf-8").split("|")
        if len(parts) != 3:
            raise ValueError("Malformed cursor structure")
        target_date = date_type.fromisoformat(parts[0])
        created_at = datetime.fromisoformat(parts[1])
        entry_id = UUID(parts[2])
        return target_date, created_at, entry_id
    except Exception as e:
        raise UnprocessableError("Invalid or malformed pagination cursor.") from e


def extract_text_from_rich_content(content: Any) -> str:
    """Recursively walks nested JSON structures to extract text strings.

    Useful for Slate, Tiptap, Lexical, and other standard editor formats.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            extract_text_from_rich_content(item) for item in content if item
        ).strip()
    if isinstance(content, dict):
        if "text" in content and isinstance(content["text"], str):
            return content["text"]

        text_vals = []
        # First check standard document container keys
        for key in ("content", "children", "root"):
            if key in content:
                extracted = extract_text_from_rich_content(content[key])
                if extracted:
                    text_vals.append(extracted)

        # Fallback to general traverse if no container key is present, skipping metadata
        if not text_vals:
            for key, val in content.items():
                if key not in (
                    "type",
                    "attrs",
                    "format",
                    "version",
                    "style",
                    "direction",
                    "mode",
                ):
                    extracted = extract_text_from_rich_content(val)
                    if extracted:
                        text_vals.append(extracted)

        return " ".join(text_vals).strip()
    return ""


class JournalService:
    """Orchestrates journal aggregates (Days) and documents (Entries) lifecycle."""

    @staticmethod
    async def create_entry(
        db: AsyncSession, user_id: UUID, data: JournalEntryCreate
    ) -> JournalEntryResponse:
        """Create a new journal entry under the resolved Day aggregate.

        Args:
            db: Database session.
            user_id: The UUID of the writing user.
            data: Entry attributes.

        Returns:
            The populated JournalEntryResponse.
        """
        day_repo = DayRepository(db)
        entry_repo = JournalRepository(db)
        tag_repo = TagRepository(db)

        # 1. Resolve Day aggregate
        day = await day_repo.get_by_date(user_id, data.date)
        if day is None:
            day = Day(user_id=user_id, date=data.date)
            day = await day_repo.create(day)

        # 2. Extract plain text representation and calculate word count
        content_text = extract_text_from_rich_content(data.content)
        word_count = len(content_text.split())

        # 3. Create entry
        entry = JournalEntry(
            day_id=day.id,
            title=data.title,
            content=data.content,
            content_text=content_text,
            word_count=word_count,
            is_favorite=data.is_favorite,
        )

        # 4. Resolve and assign tags
        tags = []
        for tag_id in data.tag_ids:
            tag = await tag_repo.get_by_id(tag_id)
            if tag is None or tag.user_id != user_id:
                raise NotFoundError(f"Tag with ID '{tag_id}' not found.")
            tags.append(tag)
        entry.tags = tags

        entry = await entry_repo.create(entry)

        # Re-fetch entry with selectinload to avoid lazy-loading
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        from app.db.models.mood import EntryMood

        stmt = (
            select(JournalEntry)
            .options(
                selectinload(JournalEntry.tags),
                selectinload(JournalEntry.moods).joinedload(EntryMood.mood),
            )
            .where(JournalEntry.id == entry.id)
        )
        res = await db.execute(stmt)
        entry = res.scalar_one()

        return JournalEntryResponse(
            id=entry.id,
            day_id=entry.day_id,
            title=entry.title,
            content=entry.content,
            content_text=entry.content_text,
            word_count=entry.word_count,
            is_favorite=entry.is_favorite,
            version=entry.version,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
            tags=[TagInfo.model_validate(t) for t in entry.tags],
            moods=[
                EntryMoodResponse(
                    id=m.mood.id,
                    name=m.mood.name,
                    color=m.mood.color,
                    intensity=m.intensity,
                )
                for m in entry.moods
            ],
        )

    @staticmethod
    async def get_entry(
        db: AsyncSession, user_id: UUID, entry_id: UUID
    ) -> JournalEntryResponse:
        """Fetch a specific journal entry verifying user ownership.

        Args:
            db: Database session.
            user_id: The UUID of the user.
            entry_id: The UUID of the entry.

        Returns:
            The JournalEntryResponse.
        """
        repo = JournalRepository(db)
        entry = await repo.get_entry_by_id(entry_id, user_id)

        if entry is None:
            raise NotFoundError("Journal entry not found.")

        return JournalEntryResponse(
            id=entry.id,
            day_id=entry.day_id,
            title=entry.title,
            content=entry.content,
            content_text=entry.content_text,
            word_count=entry.word_count,
            is_favorite=entry.is_favorite,
            version=entry.version,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
            tags=[TagInfo.model_validate(t) for t in entry.tags],
            moods=[
                EntryMoodResponse(
                    id=m.mood.id,
                    name=m.mood.name,
                    color=m.mood.color,
                    intensity=m.intensity,
                )
                for m in entry.moods
            ],
        )

    @staticmethod
    async def list_entries(
        db: AsyncSession,
        user_id: UUID,
        limit: int,
        cursor: str | None = None,
        collection_id: UUID | None = None,
        tag_id: UUID | None = None,
        target_date: date | None = None,
        is_favorite: bool | None = None,
    ) -> PaginatedJournalEntriesResponse:
        """Query paginated entries using keyset (cursor-based) pagination.

        Args:
            db: Database session.
            user_id: User UUID.
            limit: Maximum items to return.
            cursor: Optional Base64 pagination cursor string.
            collection_id: Filter by collection id.
            tag_id: Filter by tag id.
            target_date: Filter by calendar date.
            is_favorite: Filter by favorite status.

        Returns:
            The paginated entries response with next_cursor.
        """
        cursor_data = None
        if cursor is not None:
            cursor_data = decode_cursor(cursor)

        entry_repo = JournalRepository(db)
        raw_items, total = await entry_repo.get_paginated_entries(
            user_id=user_id,
            limit=limit,
            cursor_data=cursor_data,
            collection_id=collection_id,
            tag_id=tag_id,
            target_date=target_date,
            is_favorite=is_favorite,
        )

        has_next = len(raw_items) > limit
        items = list(raw_items[:limit])

        next_cursor = None
        if has_next and items:
            last_item = items[-1]
            next_cursor = encode_cursor(
                target_date=last_item.day.date,
                created_at=last_item.created_at,
                entry_id=last_item.id,
            )

        return PaginatedJournalEntriesResponse(
            items=[
                JournalEntryResponse(
                    id=e.id,
                    day_id=e.day_id,
                    title=e.title,
                    content=e.content,
                    content_text=e.content_text,
                    word_count=e.word_count,
                    is_favorite=e.is_favorite,
                    version=e.version,
                    created_at=e.created_at,
                    updated_at=e.updated_at,
                    tags=[TagInfo.model_validate(t) for t in e.tags],
                    moods=[
                        EntryMoodResponse(
                            id=m.mood.id,
                            name=m.mood.name,
                            color=m.mood.color,
                            intensity=m.intensity,
                        )
                        for m in e.moods
                    ],
                )
                for e in items
            ],
            total=total,
            next_cursor=next_cursor,
        )

    @staticmethod
    async def update_entry(
        db: AsyncSession, user_id: UUID, entry_id: UUID, data: JournalEntryUpdate
    ) -> JournalEntryResponse:
        """Update properties of an existing entry with optimistic locking check.

        Args:
            db: Database session.
            user_id: The UUID of the user.
            entry_id: The UUID of the entry.
            data: Schema updates.

        Returns:
            The updated JournalEntryResponse.
        """
        day_repo = DayRepository(db)
        tag_repo = TagRepository(db)

        # 1. Fetch entry
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        stmt = (
            select(JournalEntry)
            .options(selectinload(JournalEntry.tags))
            .where(JournalEntry.id == entry_id, JournalEntry.deleted_at.is_(None))
        )
        res = await db.execute(stmt)
        entry = res.scalar_one_or_none()

        if entry is None:
            raise NotFoundError("Journal entry not found.")

        # 2. Verify ownership
        day = await day_repo.get_by_id(entry.day_id)
        if day is None or day.user_id != user_id:
            raise NotFoundError("Journal entry not found.")

        # 3. Optimistic locking verification
        if data.version != entry.version:
            raise ConflictError("The entry has been updated by another client.")

        # 4. Modify fields
        if data.title is not None:
            entry.title = data.title

        if data.content is not None:
            entry.content = data.content
            content_text = extract_text_from_rich_content(data.content)
            entry.content_text = content_text
            entry.word_count = len(content_text.split())

        if data.is_favorite is not None:
            entry.is_favorite = data.is_favorite

        if data.tag_ids is not None:
            tags = []
            for tag_id in data.tag_ids:
                tag = await tag_repo.get_by_id(tag_id)
                if tag is None or tag.user_id != user_id:
                    raise NotFoundError(f"Tag with ID '{tag_id}' not found.")
                tags.append(tag)
            entry.tags = tags

        # 5. Flush and verify StaleDataErrors
        try:
            await db.flush()
        except StaleDataError as e:
            raise ConflictError("The entry has been updated by another client.") from e

        # Re-fetch entry with selectinload to avoid lazy-loading
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        from app.db.models.mood import EntryMood

        stmt = (
            select(JournalEntry)
            .options(
                selectinload(JournalEntry.tags),
                selectinload(JournalEntry.moods).joinedload(EntryMood.mood),
            )
            .where(JournalEntry.id == entry_id)
        )
        res = await db.execute(stmt)
        entry = res.scalar_one()

        return JournalEntryResponse(
            id=entry.id,
            day_id=entry.day_id,
            title=entry.title,
            content=entry.content,
            content_text=entry.content_text,
            word_count=entry.word_count,
            is_favorite=entry.is_favorite,
            version=entry.version,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
            tags=[TagInfo.model_validate(t) for t in entry.tags],
            moods=[
                EntryMoodResponse(
                    id=m.mood.id,
                    name=m.mood.name,
                    color=m.mood.color,
                    intensity=m.intensity,
                )
                for m in entry.moods
            ],
        )

    @staticmethod
    async def delete_entry(db: AsyncSession, user_id: UUID, entry_id: UUID) -> None:
        """Soft delete a journal entry.

        Args:
            db: Database session.
            user_id: The UUID of the user.
            entry_id: The UUID of the entry.
        """
        entry_repo = JournalRepository(db)
        day_repo = DayRepository(db)

        entry = await entry_repo.get_by_id(entry_id)
        if entry is None or entry.deleted_at is not None:
            raise NotFoundError("Journal entry not found.")

        # Check ownership
        day = await day_repo.get_by_id(entry.day_id)
        if day is None or day.user_id != user_id:
            raise NotFoundError("Journal entry not found.")

        from datetime import UTC, datetime

        entry.deleted_at = datetime.now(UTC)
        await db.flush()

    @staticmethod
    async def get_day_by_date(
        db: AsyncSession, user_id: UUID, target_date: date
    ) -> DayResponse:
        """Fetch or create daily metadata.

        Args:
            db: Database session.
            user_id: The UUID of the user.
            target_date: Calendar date to retrieve.

        Returns:
            The DayResponse.
        """
        day_repo = DayRepository(db)
        day = await day_repo.get_by_date(user_id, target_date)
        if day is None:
            day = Day(user_id=user_id, date=target_date)
            day = await day_repo.create(day)

        return DayResponse.model_validate(day)

    @staticmethod
    async def update_day(
        db: AsyncSession, user_id: UUID, target_date: date, data: DayUpdate
    ) -> DayResponse:
        """Update location or weather metadata for a calendar day.

        Args:
            db: Database session.
            user_id: User UUID.
            target_date: Calendar date.
            data: Schema updates.

        Returns:
            The updated DayResponse.
        """
        day_repo = DayRepository(db)
        day = await day_repo.get_by_date(user_id, target_date)
        if day is None:
            # Create automatically to allow setting metadata on empty days
            day = Day(user_id=user_id, date=target_date)
            day = await day_repo.create(day)

        if data.location is not None:
            day.location = data.location

        if data.weather is not None:
            day.weather = data.weather

        await db.flush()
        await db.refresh(day)

        return DayResponse.model_validate(day)

    @staticmethod
    async def list_days(
        db: AsyncSession, user_id: UUID, start_date: date, end_date: date
    ) -> list[DayResponse]:
        """List daily metadata records in a range.

        Args:
            db: Database session.
            user_id: User UUID.
            start_date: Start date.
            end_date: End date.

        Returns:
            A list of DayResponse objects.
        """
        day_repo = DayRepository(db)
        days = await day_repo.get_days_in_range(user_id, start_date, end_date)
        return [DayResponse.model_validate(d) for d in days]

    @staticmethod
    async def add_tag_to_entry(
        db: AsyncSession,
        user_id: UUID,
        entry_id: UUID,
        tag_id: UUID,
    ) -> None:
        """Attach a tag to a journal entry after verifying ownership."""
        from app.db.models.organization import JournalTag
        from app.db.repositories.journal_tag import JournalTagRepository
        from app.db.repositories.tag import TagRepository

        j_tag_repo = JournalTagRepository(db)
        tag_repo = TagRepository(db)

        # 1. Verify entry ownership
        is_owner = await j_tag_repo.verify_entry_belongs_to_user(entry_id, user_id)
        if not is_owner:
            raise NotFoundError("Journal entry not found.")

        # 2. Verify tag ownership
        tag = await tag_repo.get_by_id(tag_id)
        if tag is None or tag.user_id != user_id:
            raise NotFoundError("Tag not found.")

        # 3. Add link if not already exists
        existing = await j_tag_repo.get_by_composite_id(entry_id, tag_id)
        if existing is None:
            new_link = JournalTag(journal_entry_id=entry_id, tag_id=tag_id)
            await j_tag_repo.create(new_link)

    @staticmethod
    async def remove_tag_from_entry(
        db: AsyncSession,
        user_id: UUID,
        entry_id: UUID,
        tag_id: UUID,
    ) -> None:
        """Detach a tag from a journal entry after verifying ownership."""
        from app.db.repositories.journal_tag import JournalTagRepository
        from app.db.repositories.tag import TagRepository

        j_tag_repo = JournalTagRepository(db)
        tag_repo = TagRepository(db)

        # 1. Verify entry ownership
        is_owner = await j_tag_repo.verify_entry_belongs_to_user(entry_id, user_id)
        if not is_owner:
            raise NotFoundError("Journal entry not found.")

        # 2. Verify tag ownership
        tag = await tag_repo.get_by_id(tag_id)
        if tag is None or tag.user_id != user_id:
            raise NotFoundError("Tag not found.")

        # 3. Detach
        await j_tag_repo.delete_by_composite_id(entry_id, tag_id)

    # ------------------------------------------------------------------
    # Mood catalog
    # ------------------------------------------------------------------

    @staticmethod
    async def list_moods(db: AsyncSession) -> list[MoodResponse]:
        """Return all predefined system moods ordered by name."""
        from app.db.repositories.mood import MoodRepository

        mood_repo = MoodRepository(db)
        moods = await mood_repo.list_all()
        return [MoodResponse.model_validate(m) for m in moods]

    # ------------------------------------------------------------------
    # Entry ↔ Mood sub-resource
    # ------------------------------------------------------------------

    @staticmethod
    async def add_mood_to_entry(
        db: AsyncSession,
        user_id: UUID,
        entry_id: UUID,
        mood_id: UUID,
        intensity: int,
    ) -> None:
        """Attach a mood to a journal entry with a given intensity score."""
        from app.db.models.mood import EntryMood
        from app.db.repositories.entry_mood import EntryMoodRepository
        from app.db.repositories.mood import MoodRepository

        entry_mood_repo = EntryMoodRepository(db)
        mood_repo = MoodRepository(db)

        # 1. Verify entry ownership
        is_owner = await entry_mood_repo.verify_entry_belongs_to_user(entry_id, user_id)
        if not is_owner:
            raise NotFoundError("Journal entry not found.")

        # 2. Verify mood exists in the catalog
        mood = await mood_repo.get_by_id(mood_id)
        if mood is None:
            raise NotFoundError("Mood not found.")

        # 3. Upsert — update intensity if already linked, otherwise create
        existing = await entry_mood_repo.get_by_composite_id(entry_id, mood_id)
        if existing is None:
            await entry_mood_repo.create(
                EntryMood(
                    journal_entry_id=entry_id,
                    mood_id=mood_id,
                    intensity=intensity,
                )
            )
        else:
            existing.intensity = intensity
            await db.flush()

    @staticmethod
    async def remove_mood_from_entry(
        db: AsyncSession,
        user_id: UUID,
        entry_id: UUID,
        mood_id: UUID,
    ) -> None:
        """Detach a mood from a journal entry after verifying ownership."""
        from app.db.repositories.entry_mood import EntryMoodRepository

        entry_mood_repo = EntryMoodRepository(db)

        # 1. Verify entry ownership
        is_owner = await entry_mood_repo.verify_entry_belongs_to_user(entry_id, user_id)
        if not is_owner:
            raise NotFoundError("Journal entry not found.")

        # 2. Detach (idempotent — no error if not linked)
        await entry_mood_repo.delete_by_composite_id(entry_id, mood_id)
