"""Integration tests for the Tags V1 endpoints."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app


@pytest.mark.asyncio
async def test_tag_crud_flow(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test standard Tag creation, retrieval, listing, update, and deletion."""
    # 1. Register and login User A
    user_a_email = "user_a@example.com"
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

    # 2. Create Tag
    create_payload = {
        "name": "  WORK  ",
        "color": "#ff0000",
    }  # spaces/caps to test normalization
    create_res = await async_client.post("/api/v1/tags", json=create_payload)
    assert create_res.status_code == 201
    tag_data = create_res.json()
    assert tag_data["name"] == "work"
    assert tag_data["color"] == "#ff0000"
    assert tag_data["entry_count"] == 0
    tag_id = tag_data["id"]

    # 3. Retrieve Tag by ID
    get_res = await async_client.get(f"/api/v1/tags/{tag_id}")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "work"

    # 4. List Tags (create second tag to verify alphabetical sorting)
    await async_client.post(
        "/api/v1/tags", json={"name": "personal", "color": "#00ff00"}
    )
    list_res = await async_client.get("/api/v1/tags")
    assert list_res.status_code == 200
    tags = list_res.json()
    assert len(tags) == 2
    # Alphabetical check: "personal" then "work"
    assert tags[0]["name"] == "personal"
    assert tags[1]["name"] == "work"

    # 5. Update Tag
    update_res = await async_client.patch(
        f"/api/v1/tags/{tag_id}", json={"color": "#0000ff"}
    )
    assert update_res.status_code == 200
    assert update_res.json()["color"] == "#0000ff"

    # 6. Delete Tag
    delete_res = await async_client.delete(f"/api/v1/tags/{tag_id}")
    assert delete_res.status_code == 204

    # Verify not found in subsequent fetch
    get_again_res = await async_client.get(f"/api/v1/tags/{tag_id}")
    assert get_again_res.status_code == 404


@pytest.mark.asyncio
async def test_tag_validation_and_constraints(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test validation errors for empty names, duplicate names, and invalid color hex formats."""
    email = "validation@example.com"
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

    # Empty/whitespace name rejected
    res_empty = await async_client.post(
        "/api/v1/tags", json={"name": "   ", "color": "#fff"}
    )
    assert res_empty.status_code == 422

    # Invalid colors rejected
    for invalid_color in ["red", "#12", "#1234", "#12345", "123456"]:
        res_color = await async_client.post(
            "/api/v1/tags", json={"name": "test", "color": invalid_color}
        )
        assert res_color.status_code == 422

    # Duplicate name rejected
    await async_client.post("/api/v1/tags", json={"name": "duplicate"})
    res_dup = await async_client.post("/api/v1/tags", json={"name": "Duplicate"})
    assert res_dup.status_code == 409


@pytest.mark.asyncio
async def test_tag_permissions_isolation(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Verify that User B cannot access, modify, or delete User A's tags."""
    # Register and login User A
    user_a_email = "usera_perm@example.com"
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

    # Create tag as User A
    tag_res = await async_client.post("/api/v1/tags", json={"name": "secret-tag"})
    tag_id = tag_res.json()["id"]

    # Register and login User B using an isolated HTTP client
    user_b_email = "userb_perm@example.com"
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

        # User B lists tags — should be empty (doesn't see User A's tag)
        list_res = await client_b.get("/api/v1/tags")
        assert list_res.status_code == 200
        assert len(list_res.json()) == 0

        # User B attempts to fetch User A's tag -> 404
        get_res = await client_b.get(f"/api/v1/tags/{tag_id}")
        assert get_res.status_code == 404

        # User B attempts to modify User A's tag -> 404
        patch_res = await client_b.patch(
            f"/api/v1/tags/{tag_id}", json={"color": "#000000"}
        )
        assert patch_res.status_code == 404

        # User B attempts to delete User A's tag -> 404
        delete_res = await client_b.delete(f"/api/v1/tags/{tag_id}")
        assert delete_res.status_code == 404
