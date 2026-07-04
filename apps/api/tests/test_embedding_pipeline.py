"""Unit and integration tests for the asynchronous chunking and embedding pipeline."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from app.api.deps import get_db
from app.db.enums import EmbeddingStatus
from app.db.models import EntryMood, Mood, Tag, User
from app.db.models.ai import Embedding, JournalChunk
from app.db.models.journal import Day, JournalEntry
from app.main import app
from app.modules.embeddings.service import EmbeddingService
from app.services.embeddings import EmbeddingGenerator


@pytest_asyncio.fixture
async def custom_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session that supports real commits and manual cleanup.

    Overrides FastAPI get_db dependency.
    """
    database_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(database_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        # Override get_db on the FastAPI app
        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield session

        app.dependency_overrides[get_db] = override_get_db
        yield session

        # Manual DDL cleanup
        await session.execute(
            text(
                "TRUNCATE users, days, journal_entries, journal_chunks, embeddings CASCADE;"
            )
        )
        await session.commit()
        app.dependency_overrides.clear()

    await engine.dispose()


def test_chunk_text() -> None:
    """Test text chunking with edge cases."""
    # Empty content
    assert EmbeddingService.chunk_text("") == []
    assert EmbeddingService.chunk_text("   ") == []

    # Small content (fits in one chunk)
    content = "Hello world! This is a simple journal entry."
    chunks = EmbeddingService.chunk_text(content, max_chars=100)
    assert len(chunks) == 1
    assert chunks[0] == content

    # Long content (needs splitting)
    long_content = "a" * 1500
    chunks = EmbeddingService.chunk_text(long_content, max_chars=1000, overlap=200)
    assert len(chunks) == 2
    assert chunks[0] == "a" * 1000
    # Second chunk starts at 800 (1000 - 200 overlap) and extends for 700 chars
    assert chunks[1] == "a" * 700


@pytest.mark.asyncio
async def test_embedding_pipeline_success(custom_db_session: AsyncSession) -> None:
    """Test successful asynchronous embedding pipeline execution (mock provider)."""
    user = User(
        email=f"test_embedding_{uuid.uuid4()}@example.com",
        password_hash="fake",
        display_name="Embedding Tester",
    )
    custom_db_session.add(user)
    await custom_db_session.flush()

    day = Day(user_id=user.id, date=pytest.importorskip("datetime").date.today())
    custom_db_session.add(day)
    await custom_db_session.flush()

    entry = JournalEntry(
        day_id=day.id,
        title="My Day",
        content={
            "root": {"children": [{"text": "First paragraph. Second paragraph."}]}
        },
        content_text="First paragraph. Second paragraph.",
        word_count=4,
        is_favorite=False,
        embedding_status=EmbeddingStatus.PENDING,
    )
    custom_db_session.add(entry)
    await custom_db_session.flush()
    await custom_db_session.commit()

    # 2. Run background processor manually
    await EmbeddingService.process_entry_embeddings(
        custom_db_session, entry.id, entry.version
    )

    # 3. Reload entry and verify changes
    stmt = (
        select(JournalEntry)
        .options(
            selectinload(JournalEntry.chunks).selectinload(JournalChunk.embeddings)
        )
        .where(JournalEntry.id == entry.id)
    )
    result = await custom_db_session.execute(stmt)
    updated_entry = result.scalar_one()

    # Status must be COMPLETED
    assert updated_entry.embedding_status == EmbeddingStatus.COMPLETED

    # Verify chunks and embeddings
    assert len(updated_entry.chunks) == 1
    chunk = updated_entry.chunks[0]
    assert chunk.content == "First paragraph. Second paragraph."
    assert chunk.chunk_index == 0
    assert chunk.character_count == len(chunk.content)

    assert len(chunk.embeddings) == 1
    emb = chunk.embeddings[0]
    assert emb.provider == "mock"
    assert len(emb.embedding) == 768


@pytest.mark.asyncio
async def test_embedding_pipeline_update(custom_db_session: AsyncSession) -> None:
    """Test embedding pipeline correctly clears old chunks and updates embeddings on updates."""
    user = User(
        email=f"test_embedding_update_{uuid.uuid4()}@example.com",
        password_hash="fake",
        display_name="Embedding Tester",
    )
    custom_db_session.add(user)
    await custom_db_session.flush()

    day = Day(user_id=user.id, date=pytest.importorskip("datetime").date.today())
    custom_db_session.add(day)
    await custom_db_session.flush()

    entry = JournalEntry(
        day_id=day.id,
        title="Update Test",
        content_text="Initial content.",
        embedding_status=EmbeddingStatus.PENDING,
    )
    custom_db_session.add(entry)
    await custom_db_session.flush()
    await custom_db_session.commit()

    # 2. Run first embedding run
    await EmbeddingService.process_entry_embeddings(
        custom_db_session, entry.id, entry.version
    )

    # Verify we have one chunk and one embedding
    stmt_chunks = select(JournalChunk).where(JournalChunk.journal_entry_id == entry.id)
    chunks_res = await custom_db_session.execute(stmt_chunks)
    first_run_chunks = chunks_res.scalars().all()
    assert len(first_run_chunks) == 1
    chunk_id = first_run_chunks[0].id

    # 3. Simulate an update (version increment and content change)
    stmt_fetch = select(JournalEntry).where(JournalEntry.id == entry.id)
    res = await custom_db_session.execute(stmt_fetch)
    entry = res.scalar_one()
    entry.content_text = "Updated content that is much longer than initial content."
    entry.version += 1
    entry.embedding_status = EmbeddingStatus.PENDING
    await custom_db_session.flush()
    await custom_db_session.commit()

    # 4. Run second embedding run (pass current version, which is 2)
    await EmbeddingService.process_entry_embeddings(
        custom_db_session, entry.id, entry.version
    )

    # Verify status is COMPLETED
    res = await custom_db_session.execute(stmt_fetch)
    entry = res.scalar_one()
    assert entry.embedding_status == EmbeddingStatus.COMPLETED

    # Verify old chunk and embedding is gone
    chunks_res = await custom_db_session.execute(stmt_chunks)
    second_run_chunks = chunks_res.scalars().all()
    assert len(second_run_chunks) == 1
    assert second_run_chunks[0].id != chunk_id
    assert (
        second_run_chunks[0].content
        == "Updated content that is much longer than initial content."
    )

    # Check that database CASCADE delete cleaned up the old embedding from the embeddings table
    stmt_embs = select(Embedding).where(Embedding.chunk_id == str(chunk_id))
    embs_res = await custom_db_session.execute(stmt_embs)
    assert len(embs_res.scalars().all()) == 0


@pytest.mark.asyncio
async def test_embedding_pipeline_stale_version(
    custom_db_session: AsyncSession,
) -> None:
    """Test embedding pipeline aborts if the queued version does not match current entry version."""
    user = User(
        email=f"test_embedding_stale_{uuid.uuid4()}@example.com",
        password_hash="fake",
        display_name="Embedding Tester",
    )
    custom_db_session.add(user)
    await custom_db_session.flush()

    day = Day(user_id=user.id, date=pytest.importorskip("datetime").date.today())
    custom_db_session.add(day)
    await custom_db_session.flush()

    entry = JournalEntry(
        day_id=day.id,
        title="Stale Test",
        content_text="Some text content.",
        embedding_status=EmbeddingStatus.PENDING,
    )
    custom_db_session.add(entry)
    await custom_db_session.flush()
    await custom_db_session.commit()

    # Call with mismatched version (job version = 99, current = 1)
    await EmbeddingService.process_entry_embeddings(
        custom_db_session, entry.id, version=99
    )

    # Verify status remains PENDING and no chunks were created
    stmt = select(JournalEntry).where(JournalEntry.id == entry.id)
    res = await custom_db_session.execute(stmt)
    entry = res.scalar_one()
    assert entry.embedding_status == EmbeddingStatus.PENDING

    stmt_chunks = select(JournalChunk).where(JournalChunk.journal_entry_id == entry.id)
    chunks_res = await custom_db_session.execute(stmt_chunks)
    assert len(chunks_res.scalars().all()) == 0


@pytest.mark.asyncio
async def test_embedding_pipeline_failure_rollback(
    custom_db_session: AsyncSession,
) -> None:
    """Test failure during embedding generation rolls back database changes and sets FAILED status."""
    user = User(
        email=f"test_embedding_fail_{uuid.uuid4()}@example.com",
        password_hash="fake",
        display_name="Embedding Tester",
    )
    custom_db_session.add(user)
    await custom_db_session.flush()

    day = Day(user_id=user.id, date=pytest.importorskip("datetime").date.today())
    custom_db_session.add(day)
    await custom_db_session.flush()

    entry = JournalEntry(
        day_id=day.id,
        title="Fail Test",
        content_text="Content to embed.",
        embedding_status=EmbeddingStatus.PENDING,
    )
    custom_db_session.add(entry)
    await custom_db_session.flush()
    await custom_db_session.commit()

    # Mock the embedding provider to raise an exception
    from app.services.embeddings.provider import MockEmbeddingProvider

    with (
        patch.object(
            MockEmbeddingProvider,
            "get_embedding",
            side_effect=Exception("Embedding API error"),
        ),
        pytest.raises(Exception, match="Embedding API error"),
    ):
        await EmbeddingService.process_entry_embeddings(
            custom_db_session, entry.id, entry.version
        )

    # Verify status is FAILED and no chunks remain
    stmt = select(JournalEntry).where(JournalEntry.id == entry.id)
    res = await custom_db_session.execute(stmt)
    entry = res.scalar_one()
    assert entry.embedding_status == EmbeddingStatus.FAILED

    stmt_chunks = select(JournalChunk).where(JournalChunk.journal_entry_id == entry.id)
    chunks_res = await custom_db_session.execute(stmt_chunks)
    assert len(chunks_res.scalars().all()) == 0


@pytest.mark.asyncio
async def test_ollama_embedding_provider() -> None:
    """Test Ollama embedding provider behavior using mock HTTP responses."""
    from app.services.embeddings.provider import OllamaEmbeddingProvider

    provider = OllamaEmbeddingProvider(
        base_url="http://localhost:11434", model="nomic-embed-text"
    )
    assert provider.dimension == 768

    fake_embedding = [0.1, 0.2, 0.3, 0.4, 0.5]

    async def mock_post(*args: Any, **kwargs: Any) -> Any:
        class FakeResponse:
            def raise_for_status(self) -> None:
                pass

            def json(self) -> dict[str, Any]:
                return {"embedding": fake_embedding}

        return FakeResponse()

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        result = await provider.get_embedding("hello")
        assert result == fake_embedding
        assert provider.dimension == 5


@pytest.mark.asyncio
async def test_embedding_pipeline_with_temporal_header(
    custom_db_session: AsyncSession,
) -> None:
    """Test embedding pipeline prepends the correct date, title, tags, and moods to the embedding query."""
    import datetime

    # 1. Create a user
    user = User(
        email=f"test_temporal_{uuid.uuid4()}@example.com",
        password_hash="fake",
        display_name="Temporal Tester",
    )
    custom_db_session.add(user)
    await custom_db_session.flush()

    # 2. Create a day
    test_date = datetime.date(2026, 6, 15)
    day = Day(user_id=user.id, date=test_date)
    custom_db_session.add(day)
    await custom_db_session.flush()

    # 3. Create a journal entry
    entry = JournalEntry(
        day_id=day.id,
        title="Training for Marathon",
        content_text="First few kilometers felt comfortable.",
        embedding_status=EmbeddingStatus.PENDING,
    )
    custom_db_session.add(entry)
    await custom_db_session.flush()

    # 4. Associate tag and mood
    tag = Tag(user_id=user.id, name="running")
    custom_db_session.add(tag)

    stmt_mood = select(Mood).where(Mood.name == "happy")
    res_mood = await custom_db_session.execute(stmt_mood)
    mood = res_mood.scalar_one()

    # Load the entry with tags and moods eager loaded to avoid lazy loading issues
    stmt_fetch = (
        select(JournalEntry)
        .options(selectinload(JournalEntry.tags), selectinload(JournalEntry.moods))
        .where(JournalEntry.id == entry.id)
    )
    res_entry = await custom_db_session.execute(stmt_fetch)
    entry = res_entry.scalar_one()

    entry.tags.append(tag)
    entry_mood = EntryMood(journal_entry=entry, mood=mood, intensity=8)
    custom_db_session.add(entry_mood)
    await custom_db_session.flush()
    await custom_db_session.commit()

    # 5. Intercept the call to generate_batch
    captured_texts = []
    original_generate_batch = EmbeddingGenerator.generate_batch

    async def mock_generate_batch(self: Any, texts: list[str]) -> list[list[float]]:
        captured_texts.extend(texts)
        return await original_generate_batch(self, texts)

    # 6. Run background pipeline
    with patch.object(EmbeddingGenerator, "generate_batch", mock_generate_batch):
        await EmbeddingService.process_entry_embeddings(
            custom_db_session, entry.id, entry.version
        )

    # 7. Verify the captured text sent to generator
    assert len(captured_texts) == 1
    expected_header = "[June 15, 2026] Training for Marathon | Tags: running | Moods: happy (intensity: 8)"
    expected_full_text = f"{expected_header}\nFirst few kilometers felt comfortable."
    assert captured_texts[0] == expected_full_text

    # 8. Verify the DB chunk content is unmodified (stays raw chunk text)
    stmt = (
        select(JournalEntry)
        .options(selectinload(JournalEntry.chunks))
        .where(JournalEntry.id == entry.id)
    )
    res = await custom_db_session.execute(stmt)
    updated_entry = res.scalar_one()
    assert len(updated_entry.chunks) == 1
    assert updated_entry.chunks[0].content == "First few kilometers felt comfortable."
