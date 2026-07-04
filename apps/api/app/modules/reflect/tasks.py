"""Reflect conversational journaling background tasks."""

from __future__ import annotations

import hashlib
import logging
from datetime import date as date_type
from typing import Any
from uuid import UUID

from pydantic import AliasChoices, BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.collection import Collection, CollectionEntry
from app.db.models.journal import Day, JournalEntry
from app.db.repositories.collection import CollectionRepository
from app.db.repositories.collection_entry import CollectionEntryRepository
from app.db.repositories.journal import DayRepository, JournalRepository
from app.db.repositories.reflect import ReflectRepository
from app.services.llm import get_llm_provider

logger = logging.getLogger(__name__)


class ReflectEvaluation(BaseModel):
    """Pydantic model for Reflect binary evaluation output."""

    enough_content: str = Field(
        description="YES or NO",
        validation_alias=AliasChoices(
            "enough_content", "enough", "enough_details", "Answer", "answer", "response"
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def heal_keys(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        content_aliases = {
            "enough_content",
            "enough",
            "enough_details",
            "Answer",
            "answer",
            "response",
        }
        has_content = any(k in data for k in content_aliases)
        if has_content:
            return data

        # Look for any value that matches YES or NO (case-insensitive)
        for _, v in data.items():
            if isinstance(v, str):
                v_upper = v.strip().upper()
                if v_upper in {"YES", "NO"}:
                    data["enough_content"] = v_upper
                    return data

        # Default fallback to YES if empty/unresolved dictionary returned
        data["enough_content"] = "YES"
        return data


class ReflectEntryGeneration(BaseModel):
    """Pydantic model for Reflect journal entry generation output."""

    title: str | None = Field(
        default=None,
        description="A short title for the entry, or null",
        validation_alias=AliasChoices("title", "Title"),
    )
    content: str = Field(
        description="The journal entry text",
        validation_alias=AliasChoices("content", "Content", "entry", "journal_entry"),
    )

    @model_validator(mode="before")
    @classmethod
    def heal_keys(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        # Normalize keys/values to find title
        title_aliases = {"title", "Title"}
        content_aliases = {"content", "Content", "entry", "journal_entry"}

        # Check if we already have content matching any of the aliases
        has_content = any(k in data for k in content_aliases)
        if has_content:
            return data

        # If content is missing, search for title key and non-title keys
        found_title_key = None
        for k in data:
            if k in title_aliases:
                found_title_key = k
                break

        # Find the best candidate key for content (longest string that is not the title)
        content_candidates = []
        for k, v in data.items():
            if k == found_title_key:
                continue
            if isinstance(v, str):
                content_candidates.append(v)

        if content_candidates:
            # Pick the longest string candidate as the content
            best_candidate = max(content_candidates, key=len)
            data["content"] = best_candidate

        return data


def plain_text_to_tiptap(text: str) -> dict[str, Any]:
    """Convert plain text to Tiptap JSON format."""
    paragraphs = []
    for p in text.strip().split("\n"):
        p_clean = p.strip()
        if p_clean:
            paragraphs.append(
                {"type": "paragraph", "content": [{"type": "text", "text": p_clean}]}
            )
    return {"type": "doc", "content": paragraphs}


async def get_or_create_reflect_collection(
    db: AsyncSession, user_id: UUID
) -> Collection:
    """Retrieve the 'reflections' system collection, or create it if missing."""
    collection_repo = CollectionRepository(db)
    collection = await collection_repo.get_by_name(user_id, "reflections")
    if collection:
        return collection

    collection = Collection(
        user_id=str(user_id),
        name="reflections",
        description="Entries written by Reflect",
        icon="✨",
        is_pinned=True,
    )
    return await collection_repo.create(collection)


async def evaluate_reflect_entry(
    ctx: dict[str, Any], session_id: str, user_id: str, date_str: str
) -> None:
    """Task to check if there is enough content in today's Reflect chat to generate/update an entry."""
    db: AsyncSession = ctx["db"]
    session_id_uuid = UUID(str(session_id))
    user_id_uuid = UUID(str(user_id))
    target_date = date_type.fromisoformat(date_str)

    logger.info(
        "Evaluating reflect entry for session %s, date %s", session_id, date_str
    )

    reflect_repo = ReflectRepository(db)
    journal_repo = JournalRepository(db)

    # 1. Fetch today's messages
    messages = await reflect_repo.get_today_messages(session_id_uuid, target_date)
    if not messages:
        logger.info("No Reflect messages found for today.")
        return

    latest_msg = messages[-1]

    # 2. Heuristic check
    user_messages = [m for m in messages if m.role == "user"]
    if len(user_messages) < 3:
        logger.info("Skipping Reflect entry generation: less than 3 user messages.")
        return

    total_words = sum(len(m.content.split()) for m in user_messages)
    if total_words < 50:
        logger.info(
            "Skipping Reflect entry generation: total user words (%d) is less than 50.",
            total_words,
        )
        return

    # 3. Check if entry already written today
    reflect_entry = await reflect_repo.get_reflect_entry_by_date(
        session_id_uuid, target_date
    )
    today_entry = None
    if reflect_entry:
        today_entry = await journal_repo.get_by_id(reflect_entry.journal_entry_id)

    if today_entry and reflect_entry:
        # Check if significant new content warrants an update (>= 30 new words since last write)
        if reflect_entry.last_message_id:
            last_msg_idx = -1
            for i, m in enumerate(messages):
                if m.id == reflect_entry.last_message_id:
                    last_msg_idx = i
                    break
            new_user_messages = [
                m for m in messages[last_msg_idx + 1 :] if m.role == "user"
            ]
        else:
            new_user_messages = user_messages

        new_words = sum(len(m.content.split()) for m in new_user_messages)
        if new_words < 30:
            logger.info(
                "Skipping Reflect entry update: only %d new user words since last write (needs 30).",
                new_words,
            )
            return

    # 4. Ask LLM to evaluate
    formatted_conv = "\n".join(
        f"{'User' if m.role == 'user' else 'Reflect'}: {m.content}" for m in messages
    )
    eval_prompt = (
        "You are evaluating a conversation to decide if it contains enough\n"
        "meaningful content to write a genuine journal entry.\n\n"
        "A meaningful entry requires at least one specific moment, emotion,\n"
        "event, or reflection — not just small talk or greetings.\n\n"
        f"Conversation:\n{formatted_conv}\n\n"
        "Does this conversation contain enough to write a meaningful journal\n"
        "entry about today?\n"
        'Provide your answer in a JSON object with the key "enough_content" set to either "YES" or "NO".'
    )

    llm = get_llm_provider()
    try:
        eval_output: ReflectEvaluation = await llm.generate(
            eval_prompt, ReflectEvaluation, model=get_settings().AI_REFLECT_EVAL_MODEL
        )
        if eval_output.enough_content.strip().upper() != "YES":
            logger.info(
                "LLM evaluated conversation as not containing enough meaningful content."
            )
            return
    except Exception as exc:
        logger.exception("Error during LLM evaluation of Reflect conversation")
        raise exc

    # 5. Generate the entry
    gen_prompt = (
        "You are writing a personal journal entry on behalf of the user.\n"
        "Below is a conversation where they shared about their day.\n"
        "Write the entry in first person as if the user wrote it themselves.\n\n"
        "Guidelines:\n"
        "- Write in the user's natural voice based on how they expressed themselves.\n"
        "- Include specific details, emotions, and events they mentioned.\n"
        "- Do not add anything they did not say. Do not embellish or invent.\n"
        "- Do not mention that this was written from a conversation or by AI.\n"
        '- Do not start with "Today" — vary the opening.\n'
        "- Structure as flowing prose. No bullet points. No headers.\n"
        "- Length proportional to what was shared. Minimum 3 sentences.\n"
        "- Capture the emotional tone of the day, not just the events.\n\n"
        f"CONVERSATION:\n{formatted_conv}\n\n"
        "Write the journal entry:"
    )

    try:
        gen_output: ReflectEntryGeneration = await llm.generate(
            gen_prompt,
            ReflectEntryGeneration,
            model=get_settings().AI_REFLECT_GEN_MODEL,
        )
    except Exception as exc:
        logger.exception("Error during LLM generation of Reflect entry")
        raise exc

    content_text = gen_output.content.strip()
    word_count = len([t for t in content_text.split() if t])
    content_hash = hashlib.sha256(content_text.encode("utf-8")).hexdigest()

    try:
        if today_entry is None:
            # Create path
            # A. Resolve/create Day
            day_repo = DayRepository(db)
            day = await day_repo.get_by_date(user_id_uuid, target_date)
            if day is None:
                day = Day(user_id=str(user_id_uuid), date=target_date)
                day = await day_repo.create(day)

            # B. Create Journal Entry
            entry = JournalEntry(
                day_id=day.id,
                title=gen_output.title,
                content=plain_text_to_tiptap(content_text),
                content_text=content_text,
                content_hash=content_hash,
                word_count=word_count,
                is_favorite=False,
            )
            entry = await journal_repo.create(entry)

            # C. Create ReflectEntry linking row
            await reflect_repo.create_reflect_entry(
                session_id_uuid, entry.id, target_date, latest_msg.id
            )

            # D. Add to reflections collection
            reflect_collection = await get_or_create_reflect_collection(
                db, user_id_uuid
            )
            col_entry_repo = CollectionEntryRepository(db)
            col_entry = CollectionEntry(
                collection_id=reflect_collection.id,
                journal_entry_id=entry.id,
                position=0,
            )
            await col_entry_repo.create(col_entry)

            # E. Enqueue downstream summary/embedding tasks
            redis_pool = ctx.get("redis")
            if redis_pool:
                await redis_pool.enqueue_job(
                    "process_journal_entry_embeddings",
                    str(entry.id),
                    entry.version,
                    _queue_name="embedding_queue",
                )
                await redis_pool.enqueue_job(
                    "generate_entry_summary_task",
                    str(entry.id),
                    _queue_name="ai_queue",
                )
                await redis_pool.enqueue_job(
                    "generate_day_summary_task",
                    str(day.id),
                    _queue_name="ai_queue",
                )
            logger.info("Reflect entry %s created successfully.", entry.id)
        else:
            # Update path
            today_entry.title = gen_output.title
            today_entry.content = plain_text_to_tiptap(content_text)
            today_entry.content_text = content_text
            today_entry.content_hash = content_hash
            today_entry.word_count = word_count
            if reflect_entry:
                reflect_entry.last_message_id = latest_msg.id
            await db.flush()
            await db.refresh(today_entry)

            # Re-enqueue embedding task
            redis_pool = ctx.get("redis")
            if redis_pool:
                await redis_pool.enqueue_job(
                    "process_journal_entry_embeddings",
                    str(today_entry.id),
                    today_entry.version,
                    _queue_name="embedding_queue",
                )
            logger.info("Reflect entry %s updated successfully.", today_entry.id)

        await db.commit()
    except Exception as exc:
        logger.exception("Error committing Reflect entry creation/update")
        await db.rollback()
        raise exc
