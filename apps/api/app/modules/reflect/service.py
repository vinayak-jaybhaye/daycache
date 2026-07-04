"""Reflect service orchestrator."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from datetime import date, timedelta
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select

from app.core.config import get_settings
from app.db.enums import SummaryKind, SummaryScope
from app.db.models.ai import Summary
from app.db.models.journal import Day
from app.db.repositories.reflect import ReflectRepository
from app.services.llm import get_llm_provider

if TYPE_CHECKING:
    from arq.connections import ArqRedis
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class ReflectService:
    """Service to orchestrate Reflect conversational journaling pipeline."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def handle_message_pipeline(
        self, user_id: UUID, content: str, arq_pool: ArqRedis
    ) -> AsyncIterator[str]:
        """Validate input, manage session/messages, retrieve context, build prompts, and stream responses."""
        from app.db.repositories.settings import SettingsRepository
        from app.services.llm.personas import get_persona
        from app.services.llm.prompt_builder import build_persona_block

        settings_repo = SettingsRepository(self.db)
        user_settings = await settings_repo.get_by_user_id(user_id)
        persona_name = user_settings.ai_persona_name if user_settings else "Mira"
        persona = get_persona(persona_name)
        # 1. Validate content length
        if not content.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Message content cannot be empty.",
            )

        reflect_repo = ReflectRepository(self.db)
        today = date.today()

        # 2. Resolve session (upsert)
        session = await reflect_repo.get_or_create_session(user_id)

        # 3. Save user message immediately before any LLM call
        user_msg = await reflect_repo.save_message(
            session_id=session.id,
            role="user",
            content=content,
        )
        await self.db.flush()

        # 4. Fetch conversation context
        # A. Today's messages
        today_msgs = await reflect_repo.get_today_messages(session.id, today)
        # B. Recent messages from previous days (up to 10)
        recent_msgs = await reflect_repo.get_recent_messages(
            session.id, today, limit=10
        )

        # 5. Fetch diary context (last 7 days of summaries)
        start_date = today - timedelta(days=7)
        summary_stmt = (
            select(Summary.content, Summary.period_start)
            .where(
                Summary.user_id == str(user_id),
                Summary.scope == SummaryScope.DAY,
                Summary.kind == SummaryKind.SUMMARY,
                Summary.day_id.in_(
                    select(Day.id).where(
                        Day.user_id == user_id,
                        Day.date < today,
                        Day.date >= start_date,
                    )
                ),
            )
            .order_by(Summary.period_start.desc())
        )
        summary_res = await self.db.execute(summary_stmt)
        day_summaries = summary_res.all()

        # Define the SSE generator
        async def event_generator() -> AsyncIterator[str]:
            # Build diary summaries section
            diary_context_parts = []
            if day_summaries:
                diary_context_parts.append("RECENT DIARY CONTEXT (last 7 days):")
                for s_content, s_date in day_summaries:
                    formatted_date = (
                        s_date.strftime("%B %d, %Y") if s_date else "Unknown"
                    )
                    diary_context_parts.append(f"[{formatted_date}]\n{s_content}\n")
            diary_context_str = (
                "\n".join(diary_context_parts) if diary_context_parts else ""
            )

            # Build prompt turns for pruning
            # We combine all prev messages as turns
            all_prev_msgs = recent_msgs + [m for m in today_msgs if m.id != user_msg.id]
            turns = [{"role": m.role, "content": m.content} for m in all_prev_msgs]

            # System prompt
            system_prompt = f"""{build_persona_block(persona)}

Your role in this conversation is to talk with the user about their day
through natural, friendly conversation - not an interview.

How to talk:
- React genuinely to what the user shares before asking anything.
- Ask only one thing at a time, woven naturally into your response.
- Never ask generic questions - ask specifically about what they said.
- Match the user's energy. Follow threads. Show you were listening.
- Keep responses short: 2-4 sentences. Leave space for the user.
- If the conversation winds down naturally, let it. Don't force more.
"""

            # Prune turns to fit in token budget
            # Total input ceiling ~2020 tokens, max response 300, so target input ~1720 tokens
            while len(turns) > 6:
                prompt_lines = [system_prompt]
                if diary_context_str:
                    prompt_lines.append(diary_context_str)
                if turns:
                    recent_turns_str = "RECENT REFLECT CONVERSATIONS:\n" + "\n".join(
                        f"{'User' if t['role'] == 'user' else 'Assistant'}: {t['content']}"
                        for t in turns
                    )
                    prompt_lines.append(recent_turns_str)
                prompt_lines.append(f"Today is {today.strftime('%A, %B %d, %Y')}.")
                prompt_lines.append(f"User: {content}")
                full_prompt = "\n\n".join(prompt_lines)

                # 1 token ≈ 4 characters
                if len(full_prompt) // 4 <= 1720:
                    break
                turns.pop(0)

            # Rebuild final prompt with final/pruned turns
            prompt_lines = [system_prompt]
            if diary_context_str:
                prompt_lines.append(diary_context_str)
            if turns:
                recent_turns_str = "RECENT REFLECT CONVERSATIONS:\n" + "\n".join(
                    f"{'User' if t['role'] == 'user' else 'Assistant'}: {t['content']}"
                    for t in turns
                )
                prompt_lines.append(recent_turns_str)
            prompt_lines.append(f"Today is {today.strftime('%A, %B %d, %Y')}.")
            prompt_lines.append(f"User: {content}")
            full_prompt = "\n\n".join(prompt_lines)

            # Stream response from LLM
            provider = get_llm_provider()
            full_response_text = ""
            try:
                async for token in provider.stream(
                    full_prompt, model=get_settings().AI_REFLECT_STREAM_MODEL
                ):
                    full_response_text += token
                    yield f"data: {token}\n\n"
            except Exception:
                logger.exception("Error during LLM streaming generation")
                err_payload = json.dumps(
                    {"error": "Generation failed. Please try again."}
                )
                yield f"data: {err_payload}\n\n"
                yield "data: [DONE]\n\n"
                return

            yield "data: [DONE]\n\n"

            # Save the completed assistant message turn
            try:
                await reflect_repo.save_message(
                    session_id=session.id,
                    role="assistant",
                    content=full_response_text,
                )
                await self.db.flush()
            except Exception:
                logger.exception("Error saving assistant message response")
                return

            # Queue the entry evaluation job
            try:
                await arq_pool.enqueue_job(
                    "evaluate_reflect_entry",
                    session_id=str(session.id),
                    user_id=str(user_id),
                    date_str=str(today),
                    _queue_name="ai_queue",
                )
            except Exception:
                logger.exception("Failed to queue evaluate_reflect_entry job")

        return event_generator()
