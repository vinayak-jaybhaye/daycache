"""Integration tests for the Reflect feature."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.collection import Collection, CollectionEntry
from app.db.models.journal import Day, JournalEntry
from app.db.models.reflect import ReflectEntry, ReflectMessage, ReflectSession
from app.db.models.user import User
from app.modules.reflect.tasks import (
    ReflectEntryGeneration,
    ReflectEvaluation,
    evaluate_reflect_entry,
)


async def register_and_login(client: AsyncClient, email: str) -> dict[str, Any]:
    """Helper to register and login a user, returning user info."""
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "password123",
            "display_name": "Reflect Test User",
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
async def test_reflect_message_flow(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test full Reflect flow including session auto-creation, user msg saving, SSE stream, and arq job enqueueing."""
    await register_and_login(async_client, "reflect_flow@example.com")

    # 1. Verify history is empty initially
    history_res = await async_client.get("/api/v1/reflect/messages")
    assert history_res.status_code == 200
    assert history_res.json() == []

    # 2. Mock LLM provider for stream
    async def mock_stream(*args: Any, **kwargs: Any) -> AsyncIterator[str]:
        yield "Hello "
        yield "world!"

    mock_provider = MagicMock()
    mock_provider.stream = mock_stream

    # Setup mock arq enqueue
    mock_enqueue = AsyncMock()

    with (
        patch(
            "app.modules.reflect.service.get_llm_provider", return_value=mock_provider
        ),
        patch("arq.connections.ArqRedis.enqueue_job", mock_enqueue),
    ):
        async with async_client.stream(
            "POST",
            "/api/v1/reflect/messages",
            json={"content": "Hello Reflect!"},
        ) as res:
            assert res.status_code == 200
            lines = [line async for line in res.aiter_lines() if line]
            assert lines == ["data: Hello ", "data: world!", "data: [DONE]"]

    # Wait a bit for background saving task to complete
    await asyncio.sleep(0.1)

    # 3. Check history now has 2 messages (user & assistant)
    history_res = await async_client.get("/api/v1/reflect/messages")
    assert history_res.status_code == 200
    history_data = history_res.json()
    assert len(history_data) == 2
    assert history_data[0]["role"] == "user"
    assert history_data[0]["content"] == "Hello Reflect!"
    assert history_data[1]["role"] == "assistant"
    assert history_data[1]["content"] == "Hello world!"

    # Check today's endpoint also returns these messages
    today_res = await async_client.get("/api/v1/reflect/today")
    assert today_res.status_code == 200
    assert len(today_res.json()) == 2

    # Check arq evaluation job was enqueued
    mock_enqueue.assert_called_once()
    assert mock_enqueue.call_args[0][0] == "evaluate_reflect_entry"


@pytest.mark.asyncio
async def test_reflect_message_too_short(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test that empty messages return HTTP 422."""
    await register_and_login(async_client, "reflect_short@example.com")

    res = await async_client.post(
        "/api/v1/reflect/messages",
        json={"content": ""},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_reflect_message_stream_failure_graceful(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test that stream failures are caught, user message is still saved, and error is gracefully sent to SSE."""
    await register_and_login(async_client, "reflect_fail@example.com")

    async def mock_failed_stream(*args: Any, **kwargs: Any) -> AsyncIterator[str]:
        yield "Initial "
        raise RuntimeError("LLM Connection failure!")

    mock_provider = MagicMock()
    mock_provider.stream = mock_failed_stream

    with patch(
        "app.modules.reflect.service.get_llm_provider", return_value=mock_provider
    ):
        async with async_client.stream(
            "POST",
            "/api/v1/reflect/messages",
            json={"content": "This will fail streaming"},
        ) as res:
            assert res.status_code == 200
            lines = [line async for line in res.aiter_lines() if line]
            assert "data: Initial " in lines
            # Verify last message contains error JSON and DONE
            assert lines[-1] == "data: [DONE]"

    # Wait a bit for db flush
    await asyncio.sleep(0.1)

    # Check user message was saved despite LLM crash
    history_res = await async_client.get("/api/v1/reflect/messages")
    assert history_res.status_code == 200
    history_data = history_res.json()
    assert len(history_data) == 1
    assert history_data[0]["content"] == "This will fail streaming"


@pytest.mark.asyncio
async def test_evaluate_reflect_entry_heuristics(
    db_session: AsyncSession,
) -> None:
    """Test that arq task evaluate_reflect_entry returns early if heuristic thresholds are not met."""
    session_id = uuid4()
    target_date = date.today()

    user = User(
        email="reflect_heuristics@example.com",
        display_name="Reflect Owner",
        password_hash="test",
        is_verified=True,
    )
    db_session.add(user)
    await db_session.flush()
    user_id = user.id

    session = ReflectSession(id=session_id, user_id=user_id)
    db_session.add(session)

    # 1. Less than 3 user messages (e.g. 1 user message)
    m1 = ReflectMessage(
        session_id=session_id,
        role="user",
        content="I am typing some journal notes here to hit the threshold.",
        date=target_date,
        created_at=datetime.now(UTC),
    )
    db_session.add(m1)
    await db_session.flush()

    ctx = {"db": db_session}

    # Evaluate
    with patch.object(db_session, "commit", new=AsyncMock()):
        await evaluate_reflect_entry(
            ctx, str(session_id), str(user_id), str(target_date)
        )

    # Verify no entry exists
    stmt = select(JournalEntry).join(Day).where(Day.user_id == user_id)
    res = await db_session.execute(stmt)
    assert res.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_evaluate_reflect_entry_success(
    db_session: AsyncSession,
) -> None:
    """Test successful Reflect entry generation and insertion into reflections collection."""
    session_id = uuid4()
    target_date = date.today()

    user = User(
        email="reflect_success@example.com",
        display_name="Reflect Owner",
        password_hash="test",
        is_verified=True,
    )
    db_session.add(user)
    await db_session.flush()
    user_id = user.id

    session = ReflectSession(id=session_id, user_id=user_id)
    db_session.add(session)

    # 3 user messages with > 50 words total
    for i in range(3):
        m = ReflectMessage(
            session_id=session_id,
            role="user",
            content="Today I worked on implementing background arq tasks. It was challenging but very rewarding. I finished all core features and ran migrations.",
            date=target_date,
            created_at=datetime.now(UTC) + timedelta(minutes=i),
        )
        db_session.add(m)
    await db_session.flush()

    # Mock LLM provider returns
    mock_provider = MagicMock()
    mock_provider.generate = AsyncMock(
        side_effect=[
            ReflectEvaluation(enough_content="YES"),
            ReflectEntryGeneration(
                title="Productive Coding Session",
                content="Today went well. I implemented several background worker tasks using arq. Overall feeling accomplished.",
            ),
        ]
    )

    mock_redis = MagicMock()
    mock_redis.enqueue_job = AsyncMock()

    ctx = {"db": db_session, "redis": mock_redis}

    with (
        patch("app.modules.reflect.tasks.get_llm_provider", return_value=mock_provider),
        patch.object(db_session, "commit", new=AsyncMock()),
    ):
        await evaluate_reflect_entry(
            ctx, str(session_id), str(user_id), str(target_date)
        )

    # Verify Day was created
    stmt_day = select(Day).where(Day.user_id == user_id, Day.date == target_date)
    res_day = await db_session.execute(stmt_day)
    day = res_day.scalar_one()
    assert day is not None

    # Verify Journal Entry was created
    stmt_entry = select(JournalEntry).where(JournalEntry.day_id == day.id)
    res_entry = await db_session.execute(stmt_entry)
    entry = res_entry.scalar_one()
    assert entry.title == "Productive Coding Session"
    assert (
        entry.content_text
        == "Today went well. I implemented several background worker tasks using arq. Overall feeling accomplished."
    )

    # Verify ReflectEntry pointer table row exists
    stmt_pointer = select(ReflectEntry).where(
        ReflectEntry.session_id == session_id, ReflectEntry.date == target_date
    )
    res_pointer = await db_session.execute(stmt_pointer)
    pointer = res_pointer.scalar_one()
    assert pointer.journal_entry_id == entry.id
    assert pointer.last_message_id is not None

    # Verify entry added to reflections collection
    stmt_collection = select(Collection).where(
        Collection.user_id == user_id, Collection.name == "reflections"
    )
    res_col = await db_session.execute(stmt_collection)
    collection = res_col.scalar_one()
    assert collection.is_pinned is True

    stmt_junction = select(CollectionEntry).where(
        CollectionEntry.collection_id == collection.id,
        CollectionEntry.journal_entry_id == entry.id,
    )
    res_junction = await db_session.execute(stmt_junction)
    assert res_junction.scalar_one_or_none() is not None

    # Verify downstream embedding/summary jobs enqueued
    assert mock_redis.enqueue_job.call_count == 3
    enqueued_jobs = [call[0][0] for call in mock_redis.enqueue_job.call_args_list]
    assert "process_journal_entry_embeddings" in enqueued_jobs
    assert "generate_day_summary_task" in enqueued_jobs
    assert "generate_entry_summary_task" in enqueued_jobs


@pytest.mark.asyncio
async def test_evaluate_reflect_entry_update_path(
    db_session: AsyncSession,
) -> None:
    """Test updating Reflect entry. When new user messages are sent, check word count filter and update execution."""
    session_id = uuid4()
    target_date = date.today()

    user = User(
        email="reflect_update@example.com",
        display_name="Reflect Owner",
        password_hash="test",
        is_verified=True,
    )
    db_session.add(user)
    await db_session.flush()
    user_id = user.id

    session = ReflectSession(id=session_id, user_id=user_id)
    db_session.add(session)

    # 1. First write: 3 messages with > 50 words
    msgs = []
    for i in range(3):
        m = ReflectMessage(
            session_id=session_id,
            role="user",
            content="Today I worked on implementing background arq tasks. It was challenging but very rewarding. I finished all core features and ran migrations.",
            date=target_date,
            created_at=datetime.now(UTC) + timedelta(minutes=i),
        )
        db_session.add(m)
        msgs.append(m)
    await db_session.flush()

    # Mock first write LLM returns
    mock_provider = MagicMock()
    mock_provider.generate = AsyncMock(
        side_effect=[
            ReflectEvaluation(enough_content="YES"),
            ReflectEntryGeneration(
                title="First Write Title",
                content="First draft content description goes here.",
            ),
            # Second call (evaluation/generation)
            ReflectEvaluation(enough_content="YES"),
            ReflectEntryGeneration(
                title="Updated Title",
                content="Updated draft content description goes here with new features.",
            ),
        ]
    )

    mock_redis = MagicMock()
    mock_redis.enqueue_job = AsyncMock()
    ctx = {"db": db_session, "redis": mock_redis}

    # Run first write
    with (
        patch("app.modules.reflect.tasks.get_llm_provider", return_value=mock_provider),
        patch.object(db_session, "commit", new=AsyncMock()),
    ):
        await evaluate_reflect_entry(
            ctx, str(session_id), str(user_id), str(target_date)
        )

    # Verify ReflectEntry was created and last_message_id set
    stmt_pointer = select(ReflectEntry).where(
        ReflectEntry.session_id == session_id, ReflectEntry.date == target_date
    )
    res_pointer = await db_session.execute(stmt_pointer)
    pointer = res_pointer.scalar_one()
    assert pointer.last_message_id == msgs[-1].id

    # Verify entry content
    stmt_entry = select(JournalEntry).where(JournalEntry.id == pointer.journal_entry_id)
    res_entry = await db_session.execute(stmt_entry)
    entry = res_entry.scalar_one()
    assert entry.title == "First Write Title"

    # 2. Add a message with FEW words (e.g. 5 words) -> should skip update
    m_few = ReflectMessage(
        session_id=session_id,
        role="user",
        content="I also had dinner.",
        date=target_date,
        created_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    db_session.add(m_few)
    await db_session.flush()

    # Run task (should skip because 4 words < 30 new words since last processed message)
    with (
        patch("app.modules.reflect.tasks.get_llm_provider", return_value=mock_provider),
        patch.object(db_session, "commit", new=AsyncMock()),
    ):
        await evaluate_reflect_entry(
            ctx, str(session_id), str(user_id), str(target_date)
        )

    # Verify title is still First Write Title (skipped update)
    await db_session.refresh(entry)
    assert entry.title == "First Write Title"

    # 3. Add more messages to cross 30 words threshold
    m_more = ReflectMessage(
        session_id=session_id,
        role="user",
        content="Furthermore I went for a lovely walk around the park. The sunset was beautiful and the weather was cooling down nicely. Took a few pictures too.",
        date=target_date,
        created_at=datetime.now(UTC) + timedelta(minutes=20),
    )
    db_session.add(m_more)
    await db_session.flush()

    # Run task (should execute update)
    with (
        patch("app.modules.reflect.tasks.get_llm_provider", return_value=mock_provider),
        patch.object(db_session, "commit", new=AsyncMock()),
    ):
        await evaluate_reflect_entry(
            ctx, str(session_id), str(user_id), str(target_date)
        )

    # Verify updated content & new last_message_id
    await db_session.refresh(entry)
    assert entry.title == "Updated Title"
    await db_session.refresh(pointer)
    assert pointer.last_message_id == m_more.id


def test_reflect_entry_generation_healing_keys() -> None:
    """Test that ReflectEntryGeneration schema heals custom dictionary keys dynamically."""
    # Scenario A: only a custom key
    data_a = {
        "independence_day": "Today we had a wonderful event celebrating teamwork."
    }
    obj_a = ReflectEntryGeneration.model_validate(data_a)
    assert obj_a.content == "Today we had a wonderful event celebrating teamwork."
    assert obj_a.title is None

    # Scenario B: Title and a custom key
    data_b = {
        "Title": "Our Party",
        "some_topic": "Here is the long prose description of the party details.",
    }
    obj_b = ReflectEntryGeneration.model_validate(data_b)
    assert obj_b.title == "Our Party"
    assert obj_b.content == "Here is the long prose description of the party details."


def test_reflect_evaluation_healing_keys() -> None:
    """Test that ReflectEvaluation schema heals custom dictionary keys dynamically."""
    # Scenario A: custom key with YES
    data_a = {"some_custom_key": "YES"}
    obj_a = ReflectEvaluation.model_validate(data_a)
    assert obj_a.enough_content == "YES"

    # Scenario B: custom key with NO
    data_b = {"random_key": "no"}
    obj_b = ReflectEvaluation.model_validate(data_b)
    assert obj_b.enough_content == "NO"


def test_clean_and_parse_json() -> None:
    """Test that clean_and_parse_json robustly parses JSON with markdown wrappers and control characters."""
    from app.services.llm.provider import clean_and_parse_json

    # 1. Clean JSON
    assert clean_and_parse_json('{"key": "value"}') == {"key": "value"}

    # 2. Markdown wrapped JSON
    wrapped_json = '```json\n{\n  "key": "value"\n}\n```'
    assert clean_and_parse_json(wrapped_json) == {"key": "value"}

    # 3. Control characters inside strings (strict=False validation)
    control_char_json = '{\n  "key": "value\nwith newlines"\n}'
    assert clean_and_parse_json(control_char_json) == {"key": "value\nwith newlines"}


@pytest.mark.asyncio
async def test_gemini_provider_sdk_integration() -> None:
    """Test that GeminiLLMProvider and GeminiEmbeddingProvider use google-genai SDK correctly."""
    from unittest.mock import AsyncMock

    from app.services.embeddings.provider import GeminiEmbeddingProvider
    from app.services.llm.provider import GeminiLLMProvider

    # Test LLM provider
    provider = GeminiLLMProvider(api_key="fake-key", model="models/gemini-2.0-flash")
    assert provider.model == "gemini-2.0-flash"  # Verified prefix stripped

    mock_response = MagicMock()
    mock_response.text = '{"enough_content": "YES"}'

    provider._client.aio.models.generate_content = AsyncMock(return_value=mock_response)  # pyright: ignore[reportPrivateUsage]

    result = await provider.generate("hello", ReflectEvaluation)
    assert result.enough_content == "YES"

    # Verify exact arguments passed to the SDK
    provider._client.aio.models.generate_content.assert_called_once()  # pyright: ignore[reportPrivateUsage]
    kwargs = provider._client.aio.models.generate_content.call_args[1]  # pyright: ignore[reportPrivateUsage]
    assert kwargs["model"] == "gemini-2.0-flash"

    # Test Embedding provider
    embed_provider = GeminiEmbeddingProvider(
        api_key="fake-key", model="models/text-embedding-004"
    )
    assert embed_provider.model == "text-embedding-004"  # Verified prefix stripped

    mock_embed_val = MagicMock()
    mock_embed_val.values = [0.1, 0.2, 0.3]
    mock_embed_response = MagicMock()
    mock_embed_response.embeddings = [mock_embed_val]

    embed_provider._client.aio.models.embed_content = AsyncMock(  # pyright: ignore[reportPrivateUsage]
        return_value=mock_embed_response
    )

    embeddings = await embed_provider.get_embedding("hello")
    assert embeddings == [0.1, 0.2, 0.3]

    # Verify exact arguments passed to the SDK
    embed_provider._client.aio.models.embed_content.assert_called_once()  # pyright: ignore[reportPrivateUsage]
    kwargs_embed = embed_provider._client.aio.models.embed_content.call_args[1]  # pyright: ignore[reportPrivateUsage]
    assert kwargs_embed["model"] == "text-embedding-004"
