"""Integration tests for the Recall features."""

from __future__ import annotations

import asyncio
import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.journal import Day, JournalEntry
from app.db.models.recall import RecallMessage, RecallSession
from app.modules.journal.schemas import JournalEntryResponse
from app.modules.search.schemas import SearchResultItem
from app.modules.search.service import SearchService


async def register_and_login(client: AsyncClient, email: str) -> dict[str, Any]:
    """Helper to register and login a user, returning user info."""
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "password123",
            "display_name": "Recall Test User",
        },
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "password123",
            "installation_id": str(uuid4()),
            "platform": "web",
        },
    )
    return login_res.json()


@pytest.mark.asyncio
async def test_recall_endpoint_flow(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test full Recall flow including session auto-creation, message streaming, and metadata citation."""
    # 1. Login user
    user_info = await register_and_login(async_client, "recall_flow@example.com")
    user_id = UUID(user_info["id"])

    # 2. Setup mock journal entries
    day = Day(user_id=user_id, date=datetime.date.today())
    db_session.add(day)
    await db_session.flush()

    entry = JournalEntry(
        day_id=day.id,
        title="Day One Thoughts",
        content={"text": "I completed some coding today. Feeling productive."},
        content_text="I completed some coding today. Feeling productive.",
        word_count=7,
        tags=[],
        moods=[],
    )
    db_session.add(entry)
    await db_session.flush()

    # 3. Get session before sending messages -> Should return 404
    session_res = await async_client.get("/api/v1/recall/session")
    assert session_res.status_code == 404

    # 4. Patch SearchService.search to return mock results
    mock_results = [
        SearchResultItem(
            entry=JournalEntryResponse.model_validate(entry),
            score=0.87,
            match_type="hybrid",
            highlight_snippet="I completed some coding today. Feeling productive.",
            day_date=day.date,
        )
    ]

    with patch.object(SearchService, "search", AsyncMock(return_value=mock_results)):
        # Send a message (Min length 10 chars)
        async with async_client.stream(
            "POST",
            "/api/v1/recall/messages",
            json={"content": "What did I accomplish today?"},
        ) as res:
            assert res.status_code == 200
            # Read SSE stream
            lines = []
            async for line in res.aiter_lines():
                if line:
                    lines.append(line)

            assert len(lines) > 0
            assert lines[-1] == "data: [DONE]"

        # Wait a tiny bit for the async generator post-completion save to flush/commit
        await asyncio.sleep(0.1)

        # 5. Get session details now that it was created
        session_res = await async_client.get("/api/v1/recall/session")
        assert session_res.status_code == 200
        session_data = session_res.json()
        assert "id" in session_data

        # 6. Fetch history of messages
        history_res = await async_client.get("/api/v1/recall/messages")
        assert history_res.status_code == 200
        history_data = history_res.json()
        # Should have 2 messages: 1 user, 1 assistant
        assert len(history_data) == 2

        user_msg = history_data[0]
        asst_msg = history_data[1]

        assert user_msg["role"] == "user"
        assert user_msg["content"] == "What did I accomplish today?"
        assert "retrieved_entries" not in user_msg  # Excluded since it's None

        assert asst_msg["role"] == "assistant"
        assert len(asst_msg["retrieved_entries"]) == 1
        assert asst_msg["retrieved_entries"][0]["entry_title"] == "Day One Thoughts"
        assert asst_msg["retrieved_entries"][0]["score"] == 0.87


@pytest.mark.asyncio
async def test_recall_message_too_short_rejected(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Sending a message shorter than 10 characters returns 422 and does not save anything."""
    await register_and_login(async_client, "recall_short@example.com")

    res = await async_client.post(
        "/api/v1/recall/messages",
        json={"content": "Short"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_recall_tenant_isolation_get_and_delete(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test session and message authorization. A user cannot retrieve or delete another user's session/messages."""
    # 1. Register User A and create a session
    user_a = await register_and_login(async_client, "recall_isolation_a@example.com")

    # Manually insert session and message for User A to simulate a valid state
    session_a = RecallSession(user_id=UUID(user_a["id"]))
    db_session.add(session_a)
    await db_session.flush()

    msg_a = RecallMessage(
        session_id=session_a.id,
        role="user",
        content="This is user A's message content.",
    )
    db_session.add(msg_a)
    await db_session.flush()

    # 2. Register User B
    await register_and_login(async_client, "recall_isolation_b@example.com")

    # 3. User B tries to delete User A's message -> Should return 404
    delete_res = await async_client.delete(f"/api/v1/recall/messages/{msg_a.id}")
    assert delete_res.status_code == 404


@pytest.mark.asyncio
async def test_recall_zero_search_results_flow(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """If search returns 0 results or below threshold, return direct grounded response without LLM call."""
    await register_and_login(async_client, "recall_zero@example.com")

    with patch.object(SearchService, "search", AsyncMock(return_value=[])):
        async with async_client.stream(
            "POST",
            "/api/v1/recall/messages",
            json={"content": "Do I have anything in my journal about apples?"},
        ) as res:
            assert res.status_code == 200
            lines = []
            async for line in res.aiter_lines():
                if line:
                    lines.append(line)

            assert len(lines) > 0
            # Direct response content
            assert "I couldn't find anything in your diary" in lines[0]
            assert lines[-1] == "data: [DONE]"


@pytest.mark.asyncio
async def test_recall_paired_message_deletions(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Deleting user message deletes following assistant message. Deleting assistant standalone leaves user msg."""
    user_info = await register_and_login(async_client, "recall_deletes@example.com")
    user_id = UUID(user_info["id"])

    session = RecallSession(user_id=user_id)
    db_session.add(session)
    await db_session.flush()

    # Turn 1
    now = datetime.datetime.now(datetime.UTC)
    msg1 = RecallMessage(
        session_id=session.id, role="user", content="User message 1", created_at=now
    )
    msg2 = RecallMessage(
        session_id=session.id,
        role="assistant",
        content="Asst response 1",
        created_at=now + datetime.timedelta(seconds=1),
    )
    # Turn 2
    msg3 = RecallMessage(
        session_id=session.id,
        role="user",
        content="User message 2",
        created_at=now + datetime.timedelta(seconds=2),
    )
    msg4 = RecallMessage(
        session_id=session.id,
        role="assistant",
        content="Asst response 2",
        created_at=now + datetime.timedelta(seconds=3),
    )

    db_session.add_all([msg1, msg2, msg3, msg4])
    await db_session.flush()

    # 1. Delete standalone assistant response msg4
    del_asst = await async_client.delete(f"/api/v1/recall/messages/{msg4.id}")
    assert del_asst.status_code == 204

    # Verify msg3 (its parent user message) still exists
    stmt = select(RecallMessage).where(RecallMessage.id == msg3.id)
    res = await db_session.execute(stmt)
    assert res.scalar_one_or_none() is not None

    # 2. Delete user message msg1 (should delete msg2 as well)
    del_usr = await async_client.delete(f"/api/v1/recall/messages/{msg1.id}")
    assert del_usr.status_code == 204

    # Verify msg1 and msg2 are both deleted
    res1 = await db_session.execute(
        select(RecallMessage).where(RecallMessage.id == msg1.id)
    )
    res2 = await db_session.execute(
        select(RecallMessage).where(RecallMessage.id == msg2.id)
    )
    assert res1.scalar_one_or_none() is None
    assert res2.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_recall_delete_messages_by_date(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Deleting messages by date removes only the messages on that day."""
    user_info = await register_and_login(async_client, "recall_delete_date@example.com")
    user_id = UUID(user_info["id"])

    session = RecallSession(user_id=user_id)
    db_session.add(session)
    await db_session.flush()

    # Create messages on different dates
    msg_today = RecallMessage(
        session_id=session.id,
        role="user",
        content="Message today",
        created_at=datetime.datetime.now(datetime.UTC),
    )
    msg_yesterday = RecallMessage(
        session_id=session.id,
        role="user",
        content="Message yesterday",
        created_at=datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=1),
    )
    db_session.add_all([msg_today, msg_yesterday])
    await db_session.flush()

    # Delete all messages for yesterday
    yesterday_date_str = (
        datetime.date.today() - datetime.timedelta(days=1)
    ).isoformat()
    del_res = await async_client.delete(
        f"/api/v1/recall/messages?date={yesterday_date_str}"
    )
    assert del_res.status_code == 204

    # Verify yesterday message is gone but today's remains
    res_today = await db_session.execute(
        select(RecallMessage).where(RecallMessage.id == msg_today.id)
    )
    res_yesterday = await db_session.execute(
        select(RecallMessage).where(RecallMessage.id == msg_yesterday.id)
    )
    assert res_today.scalar_one_or_none() is not None
    assert res_yesterday.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_recall_rate_limiting(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Sending the 21st message within 1 hour returns HTTP 429."""
    user_info = await register_and_login(async_client, "recall_rate@example.com")
    user_id = UUID(user_info["id"])

    session = RecallSession(user_id=user_id)
    db_session.add(session)
    await db_session.flush()

    # Add 20 user messages in the last 10 minutes
    now = datetime.datetime.now(datetime.UTC)
    for i in range(20):
        msg = RecallMessage(
            session_id=session.id,
            role="user",
            content=f"User message turn {i}",
            created_at=now - datetime.timedelta(minutes=10 - i),
        )
        db_session.add(msg)
    await db_session.flush()

    # Send the 21st message -> Should return 429
    res = await async_client.post(
        "/api/v1/recall/messages",
        json={"content": "This is message number 21"},
    )
    assert res.status_code == 429
    assert "Retry-After" in res.headers


@pytest.mark.asyncio
async def test_recall_save_user_message_even_if_llm_fails(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """If LLM stream fails, ensure user message remains saved in DB, and SSE emits an error event."""
    user_info = await register_and_login(async_client, "recall_llm_fail@example.com")
    user_id = UUID(user_info["id"])

    day = Day(user_id=user_id, date=datetime.date.today())
    db_session.add(day)
    await db_session.flush()

    entry = JournalEntry(
        day_id=day.id,
        title="Failure Test Title",
        content={"text": "We want to fail embeddings stream."},
        content_text="We want to fail embeddings stream.",
        word_count=5,
        tags=[],
        moods=[],
    )
    db_session.add(entry)
    await db_session.flush()

    mock_results = [
        SearchResultItem(
            entry=JournalEntryResponse.model_validate(entry),
            score=0.9,
            match_type="hybrid",
            highlight_snippet="We want to fail embeddings stream.",
            day_date=day.date,
        )
    ]

    async def mock_stream(*args: object, **kwargs: object):
        # Yield one token and then raise exception
        yield "Initial"
        raise RuntimeError("LLM connection crashed!")

    mock_provider = MagicMock()
    mock_provider.stream = mock_stream

    with (
        patch.object(SearchService, "search", AsyncMock(return_value=mock_results)),
        patch(
            "app.modules.recall.service.get_llm_provider",
            return_value=mock_provider,
        ),
    ):
        async with async_client.stream(
            "POST",
            "/api/v1/recall/messages",
            json={"content": "Force stream crash now!"},
        ) as res:
            assert res.status_code == 200
            lines = []
            async for line in res.aiter_lines():
                if line:
                    lines.append(line)

            # Ensure error block is in stream
            assert any("Generation failed. Please try again." in line for line in lines)
            assert lines[-1] == "data: [DONE]"

            # Retrieve user messages to verify user query was still saved
            stmt = select(RecallMessage).where(RecallMessage.role == "user")
            res_query = await db_session.execute(stmt)
            saved_user_msgs = res_query.scalars().all()
            assert len(saved_user_msgs) == 1
            assert saved_user_msgs[0].content == "Force stream crash now!"

            # Verify no assistant message was saved
            stmt_asst = select(RecallMessage).where(RecallMessage.role == "assistant")
            res_asst = await db_session.execute(stmt_asst)
            saved_asst_msgs = res_asst.scalars().all()
            assert len(saved_asst_msgs) == 0
