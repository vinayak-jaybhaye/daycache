"""Integration tests for the Search V1 endpoints."""

from __future__ import annotations

import datetime
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import EmbeddingStatus
from app.db.models import User
from app.db.models.ai import Embedding, JournalChunk
from app.db.models.journal import Day, JournalEntry
from app.services.embeddings import get_embedding_generator


async def create_test_user(db: AsyncSession, email: str, name: str) -> User:
    """Helper to create a test user."""
    user = User(
        email=email,
        password_hash="fakehash",
        display_name=name,
    )
    db.add(user)
    await db.flush()
    return user


async def create_test_entry(
    db: AsyncSession, user_id: str, title: str, content_text: str
) -> JournalEntry:
    """Helper to create a journal entry with FTS search vector configured."""
    from sqlalchemy import select

    # Check if a Day already exists for this user and date
    stmt = select(Day).where(Day.user_id == user_id, Day.date == datetime.date.today())
    res = await db.execute(stmt)
    day = res.scalar_one_or_none()
    if day is None:
        day = Day(user_id=user_id, date=datetime.date.today())
        db.add(day)
        await db.flush()

    entry = JournalEntry(
        day_id=day.id,
        title=title,
        content={"root": {"children": [{"text": content_text}]}},
        content_text=content_text,
        word_count=len(content_text.split()),
        embedding_status=EmbeddingStatus.COMPLETED,
    )
    db.add(entry)
    await db.flush()

    # Manually populate search_vector for tests
    await db.execute(
        text(
            "UPDATE journal_entries SET search_vector = to_tsvector('english', :title || ' ' || :content) WHERE id = :id"
        ),
        {"title": title or "", "content": content_text, "id": entry.id},
    )
    await db.flush()
    return entry


async def add_entry_chunk_and_embedding(
    db: AsyncSession,
    entry: JournalEntry,
    chunk_content: str,
    embedding_vector: list[float],
    user_id: str,
) -> tuple[JournalChunk, Embedding]:
    """Helper to link chunks and embeddings to an entry."""
    chunk = JournalChunk(
        journal_entry_id=entry.id,
        chunk_index=0,
        content=chunk_content,
        content_hash="hash_" + chunk_content[:10],
        token_count=5,
        character_count=len(chunk_content),
    )
    db.add(chunk)
    await db.flush()

    embedding = Embedding(
        chunk_id=chunk.id,
        user_id=user_id,
        provider="mock",
        model="mock-model",
        embedding=embedding_vector,
    )
    db.add(embedding)
    await db.flush()
    return chunk, embedding


@pytest.mark.asyncio
async def test_search_instant_mode(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test instant/lexical search (FTS only)."""
    # 1. Register and login User A
    await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "user_search_a@example.com",
            "password": "password123",
            "display_name": "User A",
        },
    )
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": "user_search_a@example.com",
            "password": "password123",
            "installation_id": "device-a",
            "platform": "web",
        },
    )
    user_id = login_res.json()["id"]

    # 2. Populate FTS data
    entry1 = await create_test_entry(
        db_session,
        user_id,
        "Python Programming",
        "Learning lists and dictionaries in python.",
    )
    entry2 = await create_test_entry(
        db_session,
        user_id,
        "Banana Salad Recipe",
        "Mix ripe bananas with apples and delicious honey.",
    )
    await db_session.flush()

    # 3. Query FTS
    res = await async_client.get("/api/v1/search?q=python&mode=instant")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["entry"]["id"] == str(entry1.id)
    assert data[0]["match_type"] == "keyword"

    # Query with websearch quotes
    res = await async_client.get('/api/v1/search?q="banana salad"&mode=instant')
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["entry"]["id"] == str(entry2.id)

    # Empty query check
    res_empty = await async_client.get("/api/v1/search?q=   &mode=instant")
    assert res_empty.status_code == 200
    assert res_empty.json() == []


@pytest.mark.asyncio
async def test_search_semantic_mode(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test semantic search (Vector similarity only)."""
    # 1. Register and login
    await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "user_search_sem@example.com",
            "password": "password123",
            "display_name": "Semantic User",
        },
    )
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": "user_search_sem@example.com",
            "password": "password123",
            "installation_id": "device-sem",
            "platform": "web",
        },
    )
    user_id = login_res.json()["id"]

    # 2. Setup mock vectors (Dimension is 768 for tests)
    vec1 = [1.0] + [0.0] * 767
    vec2 = [0.0, 1.0] + [0.0] * 766

    entry1 = await create_test_entry(db_session, user_id, "Title 1", "Chunk text 1")
    await add_entry_chunk_and_embedding(
        db_session, entry1, "Chunk text 1", vec1, user_id
    )

    entry2 = await create_test_entry(db_session, user_id, "Title 2", "Chunk text 2")
    await add_entry_chunk_and_embedding(
        db_session, entry2, "Chunk text 2", vec2, user_id
    )
    await db_session.flush()

    # 3. Search with query matching vec1 closer
    # We patch generator.generate to return vec1
    generator = get_embedding_generator()
    with patch.object(generator, "generate", return_value=vec1):
        res = await async_client.get("/api/v1/search?q=match-vec1&mode=semantic")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 2

        # First item must be entry 1 (exact vector match -> distance 0, similarity score 1)
        assert data[0]["entry"]["id"] == str(entry1.id)
        assert abs(data[0]["score"] - 1.0) < 1e-5
        assert data[0]["match_type"] == "semantic"
        assert data[0]["highlight_snippet"] == "Chunk text 1"

        # Second item is entry 2 (orthogonal -> distance 1, similarity score 0)
        assert data[1]["entry"]["id"] == str(entry2.id)
        assert abs(data[1]["score"] - 0.0) < 1e-5


@pytest.mark.asyncio
async def test_search_hybrid_mode(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test hybrid search combining FTS and semantic results."""
    # 1. Register and login
    await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "user_search_hyb@example.com",
            "password": "password123",
            "display_name": "Hybrid User",
        },
    )
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": "user_search_hyb@example.com",
            "password": "password123",
            "installation_id": "device-hyb",
            "platform": "web",
        },
    )
    user_id = login_res.json()["id"]

    # 2. Setup entries
    # entry1 matches lexical "fruit" and semantic vec1
    entry1 = await create_test_entry(
        db_session, user_id, "Sweet Fruits", "Eating a delicious red apple."
    )
    vec1 = [1.0] + [0.0] * 767
    await add_entry_chunk_and_embedding(
        db_session, entry1, "Eating a delicious red apple.", vec1, user_id
    )

    # entry2 matches semantic vec1 but has no keyword "fruit"
    entry2 = await create_test_entry(
        db_session, user_id, "Unrelated Title", "Healthy green trees."
    )
    await add_entry_chunk_and_embedding(
        db_session, entry2, "Healthy green trees.", vec1, user_id
    )
    await db_session.flush()

    # 3. Query matching both
    generator = get_embedding_generator()
    with patch.object(generator, "generate", return_value=vec1):
        res = await async_client.get("/api/v1/search?q=fruit&mode=hybrid")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 2

        # Entry 1 should rank higher because it matched both lexical and semantic (RRF hybrid match)
        assert data[0]["entry"]["id"] == str(entry1.id)
        assert data[0]["match_type"] == "hybrid"

        # Entry 2 matched only semantic (RRF semantic-only match)
        assert data[1]["entry"]["id"] == str(entry2.id)
        assert data[1]["match_type"] == "semantic"


@pytest.mark.asyncio
async def test_search_user_isolation(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test that search queries do not return entries from other users."""
    # 1. Register User A and create entry
    await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "usera@example.com",
            "password": "password123",
            "display_name": "User A",
        },
    )
    login_a = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": "usera@example.com",
            "password": "password123",
            "installation_id": "device-a",
            "platform": "web",
        },
    )
    user_a_id = login_a.json()["id"]
    await create_test_entry(
        db_session, user_a_id, "User A Entry", "This belongs to user A."
    )
    await db_session.flush()

    # 2. Register and login User B
    await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "userb@example.com",
            "password": "password123",
            "display_name": "User B",
        },
    )
    await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": "userb@example.com",
            "password": "password123",
            "installation_id": "device-b",
            "platform": "web",
        },
    )

    # 3. Query as User B
    res = await async_client.get("/api/v1/search?q=belongs&mode=instant")
    assert res.status_code == 200
    assert res.json() == []  # User B should not see User A's entry
