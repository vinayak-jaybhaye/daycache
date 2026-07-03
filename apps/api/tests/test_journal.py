"""Integration tests for Journal Entries and Days V1 endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.journal import Day, JournalEntry
from app.db.models.tag import Tag
from app.main import app


@pytest.mark.asyncio
async def test_journal_entry_crud_and_parsing(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test creating, reading, updating, and soft-deleting journal entries with text parsing."""
    # 1. Register and login User A
    email = f"journal_crud_{uuid.uuid4().hex[:8]}@example.com"
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "display_name": "Writer"},
    )
    await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "password123",
            "installation_id": "device-journal",
            "platform": "web",
        },
    )

    # 2. Create Tag to associate
    tag_res = await async_client.post("/api/v1/tags", json={"name": "writing"})
    tag_id = tag_res.json()["id"]

    # 3. Create Entry
    rich_content = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {
                        "type": "text",
                        "text": "This is a beautiful day cache journal entry.",
                    }
                ],
            }
        ],
    }
    create_payload = {
        "date": "2026-07-03",
        "title": "A Great Day",
        "content": rich_content,
        "is_favorite": True,
        "tag_ids": [tag_id],
    }
    create_res = await async_client.post("/api/v1/entries", json=create_payload)
    assert create_res.status_code == 201
    entry_data = create_res.json()
    assert entry_data["title"] == "A Great Day"
    assert entry_data["is_favorite"] is True
    assert (
        entry_data["word_count"] == 8
    )  # "This is a beautiful day cache journal entry." = 8 words

    assert "beautiful day cache" in entry_data["content_text"]
    assert len(entry_data["tags"]) == 1
    assert entry_data["tags"][0]["name"] == "writing"
    assert entry_data["version"] == 1
    entry_id = entry_data["id"]

    # 4. Get Entry
    get_res = await async_client.get(f"/api/v1/entries/{entry_id}")
    assert get_res.status_code == 200
    assert get_res.json()["title"] == "A Great Day"

    # 5. Patch/Update Entry (Title, content, and tags)
    updated_content = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": "Shortened text."}],
            }
        ],
    }
    update_payload = {
        "title": "Modified Title",
        "content": updated_content,
        "version": 1,  # matching current version
        "tag_ids": [],  # clear tags
    }
    update_res = await async_client.patch(
        f"/api/v1/entries/{entry_id}", json=update_payload
    )
    assert update_res.status_code == 200
    updated_data = update_res.json()
    assert updated_data["title"] == "Modified Title"
    assert updated_data["word_count"] == 2  # "Shortened text." = 2 words
    assert len(updated_data["tags"]) == 0
    assert updated_data["version"] == 2

    # 6. Delete Entry (Soft Delete)
    del_res = await async_client.delete(f"/api/v1/entries/{entry_id}")
    assert del_res.status_code == 204

    # Fetching deleted entry returns 404
    get_deleted = await async_client.get(f"/api/v1/entries/{entry_id}")
    assert get_deleted.status_code == 404


@pytest.mark.asyncio
async def test_journal_entry_optimistic_locking(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test that concurrent updates with mismatched versions throw 409 Conflict."""
    email = f"optimistic_{uuid.uuid4().hex[:8]}@example.com"
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "display_name": "Writer"},
    )
    await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "password123",
            "installation_id": "device-locking",
            "platform": "web",
        },
    )

    # Create initial entry
    create_res = await async_client.post(
        "/api/v1/entries",
        json={
            "date": "2026-07-03",
            "title": "Version 1",
            "content": {"text": "hello"},
        },
    )
    entry_id = create_res.json()["id"]
    assert create_res.json()["version"] == 1

    # Client A updates with version 1 -> succeeds, increments to version 2
    update_res_a = await async_client.patch(
        f"/api/v1/entries/{entry_id}",
        json={"title": "Client A Change", "version": 1},
    )
    assert update_res_a.status_code == 200
    assert update_res_a.json()["version"] == 2

    # Client B attempts to update using outdated version 1 -> throws 409 Conflict
    update_res_b = await async_client.patch(
        f"/api/v1/entries/{entry_id}",
        json={"title": "Client B Change", "version": 1},
    )
    assert update_res_b.status_code == 409
    assert "updated by another client" in update_res_b.json()["detail"]


@pytest.mark.asyncio
async def test_journal_entries_filtering_and_pagination(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test listing entries with pagination and combinations of collection, tag, date, and favorite filters."""
    email = f"filtering_{uuid.uuid4().hex[:8]}@example.com"
    reg_res = await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "display_name": "Writer"},
    )
    user_id = UUID(reg_res.json()["id"])
    await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "password123",
            "installation_id": "device-filters",
            "platform": "web",
        },
    )

    # Create two tags and a collection
    tag_res_1 = await async_client.post("/api/v1/tags", json={"name": "tag1"})
    tag_1_id = tag_res_1.json()["id"]
    tag_res_2 = await async_client.post("/api/v1/tags", json={"name": "tag2"})
    tag_2_id = tag_res_2.json()["id"]

    col_res = await async_client.post(
        "/api/v1/collections", json={"name": "mycollection"}
    )
    col_id = col_res.json()["id"]

    # Create entries across distinct days to verify dates and ordering
    day1 = Day(user_id=user_id, date=date(2026, 7, 1))
    day2 = Day(user_id=user_id, date=date(2026, 7, 2))
    db_session.add_all([day1, day2])
    await db_session.flush()

    # Entry 1: day 1, favorite, tag1
    e1 = JournalEntry(
        day_id=day1.id,
        title="First Entry",
        content={},
        is_favorite=True,
        created_at=datetime.now(UTC) - timedelta(minutes=10),
    )
    db_session.add(e1)
    await db_session.flush()

    # Link tag 1 to e1
    await async_client.post("/api/v1/tags", json={"name": "dummy"})  # flush session
    stmt_tag_link_1 = f"INSERT INTO journal_tags (journal_entry_id, tag_id) VALUES ('{e1.id}', '{tag_1_id}')"
    await db_session.execute(select(Tag))  # keep ORM updated
    from sqlalchemy import text

    await db_session.execute(text(stmt_tag_link_1))

    # Entry 2: day 2, draft, collection mapped, tag2
    e2 = JournalEntry(
        day_id=day2.id,
        title="Second Entry",
        content={},
        created_at=datetime.now(UTC) - timedelta(minutes=5),
    )

    db_session.add(e2)
    await db_session.flush()

    stmt_tag_link_2 = f"INSERT INTO journal_tags (journal_entry_id, tag_id) VALUES ('{e2.id}', '{tag_2_id}')"
    stmt_col_link = f"INSERT INTO collection_entries (collection_id, journal_entry_id, position) VALUES ('{col_id}', '{e2.id}', 0)"
    await db_session.execute(text(stmt_tag_link_2))
    await db_session.execute(text(stmt_col_link))
    await db_session.flush()

    # 1. Fetch all entries (no filters) -> returns both
    all_res = await async_client.get("/api/v1/entries")
    assert all_res.status_code == 200
    assert all_res.json()["total"] == 2
    # Sorting check: day 2 comes before day 1 (date desc)
    assert all_res.json()["items"][0]["title"] == "Second Entry"

    # 2. Filter by tag 1
    tag_res = await async_client.get(f"/api/v1/entries?tag_id={tag_1_id}")
    assert len(tag_res.json()["items"]) == 1
    assert tag_res.json()["items"][0]["title"] == "First Entry"

    # 3. Filter by collection
    col_filter_res = await async_client.get(f"/api/v1/entries?collection_id={col_id}")
    assert len(col_filter_res.json()["items"]) == 1
    assert col_filter_res.json()["items"][0]["title"] == "Second Entry"

    # 4. Filter by favorite
    fav_res = await async_client.get("/api/v1/entries?is_favorite=true")
    assert len(fav_res.json()["items"]) == 1
    assert fav_res.json()["items"][0]["title"] == "First Entry"

    # 5. Keyset pagination test: page 1 with limit=1
    page1_res = await async_client.get("/api/v1/entries?limit=1")
    assert page1_res.status_code == 200
    page1_data = page1_res.json()
    assert len(page1_data["items"]) == 1
    assert page1_data["items"][0]["title"] == "Second Entry"
    assert page1_data["next_cursor"] is not None

    # Keyset pagination test: page 2 using cursor
    cursor = page1_data["next_cursor"]
    page2_res = await async_client.get(f"/api/v1/entries?limit=1&cursor={cursor}")
    assert page2_res.status_code == 200
    page2_data = page2_res.json()
    assert len(page2_data["items"]) == 1
    assert page2_data["items"][0]["title"] == "First Entry"
    assert page2_data["next_cursor"] is None


@pytest.mark.asyncio
async def test_days_metadata_lifecycle(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test getting, listing, and updating daily aggregate metadata (location/weather)."""
    email = f"days_{uuid.uuid4().hex[:8]}@example.com"
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "display_name": "User"},
    )
    await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "password123",
            "installation_id": "device-days",
            "platform": "web",
        },
    )

    # Get a day implicitly creates it
    get_res = await async_client.get("/api/v1/days/2026-07-03")
    assert get_res.status_code == 200
    day_data = get_res.json()
    assert day_data["date"] == "2026-07-03"
    assert day_data["weather"] is None

    # Patch daily metadata
    weather = {"temp": 24, "condition": "sunny"}
    location = {"city": "San Francisco", "lat": 37.77, "lon": -122.41}
    patch_res = await async_client.patch(
        "/api/v1/days/2026-07-03", json={"weather": weather, "location": location}
    )
    assert patch_res.status_code == 200
    updated_data = patch_res.json()
    assert updated_data["weather"]["temp"] == 24
    assert updated_data["location"]["city"] == "San Francisco"

    # List days in range
    list_res = await async_client.get(
        "/api/v1/days?start_date=2026-07-01&end_date=2026-07-05"
    )
    assert list_res.status_code == 200
    days = list_res.json()
    assert len(days) == 1
    assert days[0]["date"] == "2026-07-03"


@pytest.mark.asyncio
async def test_journal_owner_permissions_isolation(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Verify that User B cannot read or modify User A's entries or day aggregates."""
    # Register and login User A
    user_a_email = f"usera_j_{uuid.uuid4().hex[:8]}@example.com"
    await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": user_a_email,
            "password": "password123",
            "display_name": "User A",
        },
    )
    await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": user_a_email,
            "password": "password123",
            "installation_id": "device-a",
            "platform": "web",
        },
    )

    # Create entry as User A
    create_res = await async_client.post(
        "/api/v1/entries",
        json={"date": "2026-07-03", "title": "Secret A", "content": {}},
    )
    entry_id = create_res.json()["id"]

    # Register and login User B via isolated client
    user_b_email = f"userb_j_{uuid.uuid4().hex[:8]}@example.com"
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client_b:
        await client_b.post(
            "/api/v1/auth/register",
            json={
                "email": user_b_email,
                "password": "password123",
                "display_name": "User B",
            },
        )
        await client_b.post(
            "/api/v1/auth/login",
            json={
                "email": user_b_email,
                "password": "password123",
                "installation_id": "device-b",
                "platform": "web",
            },
        )

        # 1. User B lists entries — should not see User A's entry
        list_res = await client_b.get("/api/v1/entries")
        assert list_res.status_code == 200
        assert list_res.json()["total"] == 0

        # 2. User B tries to fetch User A's entry details -> 404
        get_res = await client_b.get(f"/api/v1/entries/{entry_id}")
        assert get_res.status_code == 404

        # 3. User B tries to update User A's entry -> 404
        patch_res = await client_b.patch(
            f"/api/v1/entries/{entry_id}", json={"title": "Hack", "version": 1}
        )
        assert patch_res.status_code == 404

        # 4. User B tries to delete User A's entry -> 404
        delete_res = await client_b.delete(f"/api/v1/entries/{entry_id}")
        assert delete_res.status_code == 404

        # 5. User B tries to update User A's day aggregate location -> creates/modifies User B's own day instead
        day_res = await client_b.patch(
            "/api/v1/days/2026-07-03", json={"location": {"city": "Boston"}}
        )
        assert day_res.status_code == 200

        # Verify User A's day metadata remains unaffected
        day_a_res = await async_client.get("/api/v1/days/2026-07-03")
        assert day_a_res.json()["location"] is None


@pytest.mark.asyncio
async def test_journal_entry_tag_association(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Verify linking and unlinking tags to/from journal entries via sub-resource endpoints."""
    # 1. Register & login
    email = "tag-assoc@example.com"
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "display_name": "Assoc"},
    )
    await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "password123",
            "installation_id": "assoc-d",
            "platform": "web",
        },
    )

    # 2. Create Tag
    tag_res = await async_client.post("/api/v1/tags", json={"name": "vacation"})
    assert tag_res.status_code == 201
    tag_id = tag_res.json()["id"]

    # 3. Create Entry
    entry_res = await async_client.post(
        "/api/v1/entries",
        json={
            "date": "2026-07-04",
            "title": "Roadtrip to mountains",
            "content": {},
            "is_favorite": False,
        },
    )
    assert entry_res.status_code == 201
    entry_id = entry_res.json()["id"]

    # Verify no tags initially
    assert len(entry_res.json()["tags"]) == 0

    # 4. Attach Tag using POST /entries/{id}/tags
    link_res = await async_client.post(
        f"/api/v1/entries/{entry_id}/tags",
        json={"tag_id": tag_id},
    )
    assert link_res.status_code == 204

    # Verify tag is attached
    get_res = await async_client.get(f"/api/v1/entries/{entry_id}")
    assert get_res.status_code == 200
    tags = get_res.json()["tags"]
    assert len(tags) == 1
    assert tags[0]["id"] == tag_id
    assert tags[0]["name"] == "vacation"

    # 5. Detach Tag using DELETE /entries/{id}/tags/{tag_id}
    unlink_res = await async_client.delete(f"/api/v1/entries/{entry_id}/tags/{tag_id}")
    assert unlink_res.status_code == 204

    # Verify tag is detached
    get_res_2 = await async_client.get(f"/api/v1/entries/{entry_id}")
    assert get_res_2.status_code == 200
    assert len(get_res_2.json()["tags"]) == 0


@pytest.mark.asyncio
async def test_list_moods(async_client: AsyncClient, db_session: AsyncSession) -> None:
    """GET /moods returns the full seeded mood catalog without requiring auth."""
    res = await async_client.get("/api/v1/moods")
    assert res.status_code == 200
    moods = res.json()

    # All 16 predefined moods should be returned
    assert len(moods) == 16

    # Ordered by name ascending
    names = [m["name"] for m in moods]
    assert names == sorted(names)

    # Spot-check first mood
    first = moods[0]
    assert first["name"] == "angry"
    assert first["color"] == "#EF5350"


@pytest.mark.asyncio
async def test_entry_mood_association(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Verify linking and unlinking moods to/from journal entries via sub-resource endpoints."""
    # 1. Register & login
    email = "mood-assoc@example.com"
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "display_name": "Moody"},
    )
    await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "password123",
            "installation_id": "mood-d",
            "platform": "web",
        },
    )

    # 2. Fetch the mood catalog and pick "happy"
    moods_res = await async_client.get("/api/v1/moods")
    assert moods_res.status_code == 200
    moods = moods_res.json()
    happy = next(m for m in moods if m["name"] == "happy")
    mood_id = happy["id"]

    # 3. Create a journal entry
    entry_res = await async_client.post(
        "/api/v1/entries",
        json={
            "date": "2026-07-04",
            "title": "A great day",
            "content": {},
            "is_favorite": False,
        },
    )
    assert entry_res.status_code == 201
    entry_id = entry_res.json()["id"]
    assert len(entry_res.json()["moods"]) == 0

    # 4. Attach mood with intensity 8
    link_res = await async_client.post(
        f"/api/v1/entries/{entry_id}/moods",
        json={"mood_id": mood_id, "intensity": 8},
    )
    assert link_res.status_code == 204

    # Verify mood appears on the entry with correct intensity
    get_res = await async_client.get(f"/api/v1/entries/{entry_id}")
    assert get_res.status_code == 200
    entry_moods = get_res.json()["moods"]
    assert len(entry_moods) == 1
    assert entry_moods[0]["id"] == mood_id
    assert entry_moods[0]["name"] == "happy"
    assert entry_moods[0]["intensity"] == 8

    # 5. Update intensity via re-link (upsert)
    relink_res = await async_client.post(
        f"/api/v1/entries/{entry_id}/moods",
        json={"mood_id": mood_id, "intensity": 3},
    )
    assert relink_res.status_code == 204

    get_res2 = await async_client.get(f"/api/v1/entries/{entry_id}")
    assert get_res2.json()["moods"][0]["intensity"] == 3

    # 6. Detach mood
    unlink_res = await async_client.delete(
        f"/api/v1/entries/{entry_id}/moods/{mood_id}"
    )
    assert unlink_res.status_code == 204

    get_res3 = await async_client.get(f"/api/v1/entries/{entry_id}")
    assert get_res3.status_code == 200
    assert len(get_res3.json()["moods"]) == 0
