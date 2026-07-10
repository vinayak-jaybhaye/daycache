"""Recall service orchestrator."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import HTTPException, status

from app.core.config import get_settings
from app.db.repositories.recall import RecallRepository
from app.modules.search.service import SearchService
from app.services.llm import get_llm_provider

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class RecallService:
    """Service to orchestrate Recall memory retrieval pipeline."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def handle_message_pipeline(
        self, user_id: UUID, content: str
    ) -> AsyncIterator[str]:
        """Validate input, manage session/messages, retrieve context, build prompts, and stream responses."""
        # 1. Validate content length
        if len(content) < 1:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Message must be at least 1 character.",
            )

        settings = get_settings()
        recall_repo = RecallRepository(self.db)
        from app.db.repositories.settings import SettingsRepository
        from app.services.llm.personas import get_persona
        from app.services.llm.prompt_builder import build_persona_block

        settings_repo = SettingsRepository(self.db)
        user_settings = await settings_repo.get_by_user_id(user_id)
        persona_name = user_settings.ai_persona_name if user_settings else "Mira"
        persona = get_persona(persona_name)

        # 2. Resolve session
        session = await recall_repo.get_or_create_session(user_id)

        # 3. Check rate limit
        now = datetime.now(UTC)
        one_hour_ago = now - timedelta(hours=1)
        user_msgs_in_hour = await recall_repo.get_session_history(
            session_id=session.id,
            before=None,
            date_filter=None,
            limit=settings.RECALL_RATE_LIMIT
            + 5,  # Fetch slightly more than rate limit to count/find oldest
        )
        # Filter for user messages sent within the last hour
        user_msgs = [
            m
            for m in user_msgs_in_hour
            if m.role == "user" and m.created_at.replace(tzinfo=UTC) > one_hour_ago
        ]

        if len(user_msgs) >= settings.RECALL_RATE_LIMIT:
            # Sort user_msgs by created_at to find the oldest
            user_msgs.sort(key=lambda m: m.created_at)
            oldest_msg = user_msgs[0]
            oldest_msg_tz = oldest_msg.created_at.replace(tzinfo=UTC)
            reset_time = oldest_msg_tz + timedelta(hours=1)
            retry_after = int((reset_time - now).total_seconds())
            if retry_after < 0:
                retry_after = 0

            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again later.",
                headers={"Retry-After": str(retry_after)},
            )

        # 4. Save user message immediately
        user_msg = await recall_repo.save_message(
            session_id=session.id,
            role="user",
            content=content,
        )
        await self.db.flush()

        # Define the SSE generator
        async def event_generator() -> AsyncIterator[str]:
            import json

            search_service = SearchService(self.db)
            try:
                results = await search_service.search(
                    query=content,
                    user_id=user_id,
                    mode="hybrid",
                    limit=8,
                    context=True,
                )
            except Exception:
                logger.exception(
                    "SearchService failed during Recall message processing"
                )
                err_payload = json.dumps(
                    {"error": "Generation failed. Please try again."}
                )
                yield f"data: {err_payload}\n\n"
                yield "data: [DONE]\n\n"
                return

            # Filter by relevance threshold
            valid_results = [
                r for r in results if r.score >= settings.RECALL_RELEVANCE_THRESHOLD
            ]
            no_entries_found = len(valid_results) == 0

            if no_entries_found:
                # Direct response without LLM call
                direct_response = (
                    "I couldn't find anything in your diary related to that. "
                    "Try writing about it first."
                )
                yield f"data: {direct_response}\n\n"
                yield "data: [DONE]\n\n"

                # Save assistant response
                await recall_repo.save_message(
                    session_id=session.id,
                    role="assistant",
                    content=direct_response,
                    retrieved_entries=None,
                )
                await self.db.flush()
                return

            # Eager load history context
            try:
                history = await recall_repo.get_session_history(session.id, limit=10)
            except Exception:
                logger.exception("Error loading session history")
                err_payload = json.dumps(
                    {"error": "Generation failed. Please try again."}
                )
                yield f"data: {err_payload}\n\n"
                yield "data: [DONE]\n\n"
                return

            # Build System prompt
            system_prompt = f"""{build_persona_block(persona)}

Your role in this conversation is memory retrieval — helping the user
understand their own past by answering questions grounded strictly
in their journal entries.

Rules:
- Answer only from the journal context provided. Never use outside knowledge.
- If the context does not contain enough information, say so honestly.
- Always reference which entry or date your answer comes from.
- Never invent details the user did not write.
- Refer to the user in second person: "you wrote", "you mentioned".
- If no journal context is provided, respond:
  "I couldn't find anything in your diary related to that."
"""

            # Build Journal Context (chronological by date)
            sorted_results = sorted(valid_results, key=lambda x: x.day_date or date.min)
            context_parts = ["--- YOUR JOURNAL ---"]
            for res in sorted_results:
                formatted_date = (
                    res.day_date.strftime("%B %d, %Y")
                    if res.day_date
                    else "Unknown Date"
                )
                title_part = f' — "{res.entry.title}"' if res.entry.title else ""
                context_parts.append(
                    f"[{formatted_date}{title_part}]\n{res.highlight_snippet or ''}\n"
                )
            context_parts.append("--- END ---")
            context_str = "\n".join(context_parts)

            # Prune conversation history to fit within the 4300 token budget (chronological)
            turns = [
                {"role": m.role, "content": m.content}
                for m in history
                if m.id != user_msg.id
            ]
            while True:
                prompt_lines = [system_prompt, context_str]
                for turn in turns:
                    role_name = "User" if turn["role"] == "user" else "Assistant"
                    prompt_lines.append(f"{role_name}: {turn['content']}")
                prompt_lines.append(f"User: {content}")
                full_prompt = "\n\n".join(prompt_lines)

                # Token count estimate (1 token approx 4 characters)
                total_tokens = len(full_prompt) // 4
                if total_tokens <= 4300 or not turns:
                    break
                # Drop oldest conversation turn
                turns.pop(0)

            # Stream response from LLM
            provider = get_llm_provider()
            full_response_text = ""
            try:
                async for token in provider.stream(full_prompt):
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

            # Save the completed assistant message turn with metadata citation
            retrieved_metadata = []
            for r in valid_results:
                retrieved_metadata.append(
                    {
                        "entry_id": str(r.entry.id),
                        "entry_title": r.entry.title,
                        "day_date": r.day_date.isoformat() if r.day_date else None,
                        "score": round(float(r.score), 4),
                        "snippet": r.highlight_snippet,
                    }
                )

            try:
                await recall_repo.save_message(
                    session_id=session.id,
                    role="assistant",
                    content=full_response_text,
                    retrieved_entries=retrieved_metadata,
                )
                await self.db.flush()
            except Exception:
                logger.exception("Error saving assistant message response")

        return event_generator()
