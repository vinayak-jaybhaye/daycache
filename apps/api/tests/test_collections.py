"""Integration tests for the Collections V1 endpoints."""

from __future__ import annotations

from datetime import date
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.journal import Day, JournalEntry
from app.main import app


@pytest.mark.asyncio
async def test_collection_crud_flow(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test standard Collection creation, retrieval, listing, update, and deletion."""
    # 1. Register and login User A
    user_email = "col_crud@example.com"
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": user_email, "password": "password123", "display_name": "User"},
    )
    await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": user_email,
            "password": "password123",
            "installation_id": "device-col",
            "platform": "web",
        },
    )

    # 2. Create Collection
    create_payload = {
        "name": "  TRAVELS  ",
        "description": "Places visited",
        "icon": "airplane",
        "is_pinned": True,
    }
    create_res = await async_client.post("/api/v1/collections", json=create_payload)
    assert create_res.status_code == 201
    col_data = create_res.json()
    assert col_data["name"] == "travels"
    assert col_data["description"] == "Places visited"
    assert col_data["icon"] == "airplane"
    assert col_data["is_pinned"] is True
    assert col_data["entry_count"] == 0
    col_id = col_data["id"]

    # 3. Retrieve Collection by ID
    get_res = await async_client.get(f"/api/v1/collections/{col_id}")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "travels"

    # 4. List Collections (create second unpinned collection to verify sorting)
    await async_client.post(
        "/api/v1/collections", json={"name": "ideas", "is_pinned": False}
    )
    list_res = await async_client.get("/api/v1/collections")
    assert list_res.status_code == 200
    cols = list_res.json()
    assert len(cols) == 2
    # Pinned first sorting: "travels" (is_pinned=True) then "ideas" (is_pinned=False)
    assert cols[0]["name"] == "travels"
    assert cols[1]["name"] == "ideas"

    # 5. Update Collection
    update_res = await async_client.patch(
        f"/api/v1/collections/{col_id}", json={"is_pinned": False, "description": "New"}
    )
    assert update_res.status_code == 200
    assert update_res.json()["is_pinned"] is False
    assert update_res.json()["description"] == "New"

    # 6. Delete Collection
    delete_res = await async_client.delete(f"/api/v1/collections/{col_id}")
    assert delete_res.status_code == 204

    # Verify not found in subsequent fetch
    get_again_res = await async_client.get(f"/api/v1/collections/{col_id}")
    assert get_again_res.status_code == 404


@pytest.mark.asyncio
async def test_collection_uniqueness_constraints(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test duplicate collection names per user are rejected."""
    email = "col_constraints@example.com"
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "display_name": "Val"},
    )
    await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "password123",
            "installation_id": "device-val",
            "platform": "web",
        },
    )

    # Empty name rejected
    res_empty = await async_client.post("/api/v1/collections", json={"name": "   "})
    assert res_empty.status_code == 422

    # Duplicate name rejected
    await async_client.post("/api/v1/collections", json={"name": "unique"})
    res_dup = await async_client.post("/api/v1/collections", json={"name": "Unique"})
    assert res_dup.status_code == 409


@pytest.mark.asyncio
async def test_collection_entries_mapping(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test adding, removing, and counting entries associated with a collection."""
    # 1. Register and login User A
    user_email = "col_entries@example.com"
    reg_res = await async_client.post(
        "/api/v1/auth/register",
        json={"email": user_email, "password": "password123", "display_name": "User"},
    )
    user_id = UUID(reg_res.json()["id"])
    await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": user_email,
            "password": "password123",
            "installation_id": "device-col",
            "platform": "web",
        },
    )

    # 2. Create Collection
    col_res = await async_client.post("/api/v1/collections", json={"name": "memories"})
    col_id = col_res.json()["id"]

    # 3. Create a test journal entry in the DB for User A
    day = Day(user_id=user_id, date=date.today())
    db_session.add(day)
    await db_session.flush()

    entry = JournalEntry(day_id=day.id, title="My trip to Paris", content={})
    db_session.add(entry)
    await db_session.flush()
    entry_id = entry.id

    # 4. Associate entry to collection
    add_res = await async_client.post(
        f"/api/v1/collections/{col_id}/entries",
        json={"journal_entry_id": str(entry_id)},
    )
    assert add_res.status_code == 204

    # 5. Fetch collection — check entry_count is 1
    get_res = await async_client.get(f"/api/v1/collections/{col_id}")
    assert get_res.status_code == 200
    assert get_res.json()["entry_count"] == 1

    # 6. Idempotency check: Associate same entry again
    add_dup_res = await async_client.post(
        f"/api/v1/collections/{col_id}/entries",
        json={"journal_entry_id": str(entry_id)},
    )
    assert add_dup_res.status_code == 204
    # count remains 1
    get_dup_res = await async_client.get(f"/api/v1/collections/{col_id}")
    assert get_dup_res.json()["entry_count"] == 1

    # 7. Disassociate entry
    del_res = await async_client.delete(
        f"/api/v1/collections/{col_id}/entries/{entry_id}"
    )
    assert del_res.status_code == 204

    # count returns to 0
    get_del_res = await async_client.get(f"/api/v1/collections/{col_id}")
    assert get_del_res.json()["entry_count"] == 0

    # Idempotency check: remove same entry again
    del_dup_res = await async_client.delete(
        f"/api/v1/collections/{col_id}/entries/{entry_id}"
    )
    assert del_dup_res.status_code == 204


@pytest.mark.asyncio
async def test_collection_permissions_isolation(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Verify that User B cannot read, edit, delete, or link entries to User A's collections."""
    # Register and login User A
    user_a_email = "usera_col@example.com"
    reg_a_res = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": user_a_email,
            "password": "password123",
            "display_name": "User A",
        },
    )
    user_a_id = UUID(reg_a_res.json()["id"])
    await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": user_a_email,
            "password": "password123",
            "installation_id": "device-a",
            "platform": "web",
        },
    )

    # Create collection and journal entry as User A
    col_res = await async_client.post(
        "/api/v1/collections", json={"name": "user-a-col"}
    )
    col_id = col_res.json()["id"]

    day_a = Day(user_id=user_a_id, date=date.today())
    db_session.add(day_a)
    await db_session.flush()
    entry_a = JournalEntry(day_id=day_a.id, title="User A Entry", content={})
    db_session.add(entry_a)
    await db_session.flush()
    entry_a_id = entry_a.id

    # Register and login User B using an isolated client
    user_b_email = "userb_col@example.com"
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client_b:
        reg_b_res = await client_b.post(
            "/api/v1/auth/register",
            json={
                "email": user_b_email,
                "password": "password123",
                "display_name": "User B",
            },
        )
        user_b_id = UUID(reg_b_res.json()["id"])
        await client_b.post(
            "/api/v1/auth/login",
            json={
                "email": user_b_email,
                "password": "password123",
                "installation_id": "device-b",
                "platform": "web",
            },
        )

        # Create collection and journal entry as User B
        col_b_res = await client_b.post(
            "/api/v1/collections", json={"name": "user-b-col"}
        )
        col_b_id = col_b_res.json()["id"]

        day_b = Day(user_id=user_b_id, date=date.today())
        db_session.add(day_b)
        await db_session.flush()
        entry_b = JournalEntry(day_id=day_b.id, title="User B Entry", content={})
        db_session.add(entry_b)
        await db_session.flush()
        entry_b_id = entry_b.id

        # 1. User B attempts to read User A's collection -> 404
        get_res = await client_b.get(f"/api/v1/collections/{col_id}")
        assert get_res.status_code == 404

        # 2. User B attempts to patch User A's collection -> 404
        patch_res = await client_b.patch(
            f"/api/v1/collections/{col_id}", json={"icon": "test"}
        )
        assert patch_res.status_code == 404

        # 3. User B attempts to delete User A's collection -> 404
        delete_res = await client_b.delete(f"/api/v1/collections/{col_id}")
        assert delete_res.status_code == 404

        # 4. User B attempts to associate User B's entry with User A's collection -> 404
        add_to_a_res = await client_b.post(
            f"/api/v1/collections/{col_id}/entries",
            json={"journal_entry_id": str(entry_b_id)},
        )
        assert add_to_a_res.status_code == 404

        # 5. User B attempts to associate User A's entry with User B's collection -> 404
        add_a_entry_res = await client_b.post(
            f"/api/v1/collections/{col_b_id}/entries",
            json={"journal_entry_id": str(entry_a_id)},
        )
        assert add_a_entry_res.status_code == 404
