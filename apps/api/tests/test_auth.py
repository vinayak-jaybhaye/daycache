"""Integration tests for the Authentication V1 endpoints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.config import get_settings
from app.db.models import Device, User
from app.db.models import Session as UserSession
from app.main import app


@pytest.mark.asyncio
async def test_register_success(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test successful user registration creates user and settings."""
    payload = {
        "email": "Test_Register@Example.Com",  # Mixed case to test normalisation
        "password": "securepassword123",
        "display_name": "Test User",
    }
    response = await async_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["email"] == "test_register@example.com"  # Normalised to lowercase
    assert data["display_name"] == "Test User"
    assert data["is_verified"] is False
    assert "id" in data

    # Verify record in DB
    result = await db_session.execute(
        select(User)
        .options(joinedload(User.settings))
        .where(User.email == "test_register@example.com")
    )
    user = result.scalar_one_or_none()
    assert user is not None
    assert user.display_name == "Test User"
    assert user.settings is not None
    assert user.settings.locale == "en-US"


@pytest.mark.asyncio
async def test_register_duplicate_email(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test registering a duplicate email (even with different case) returns 409."""
    payload1 = {
        "email": "John@Example.com",
        "password": "securepassword123",
        "display_name": "User One",
    }
    response = await async_client.post("/api/v1/auth/register", json=payload1)
    assert response.status_code == 201

    # Register with different casing
    payload2 = {
        "email": "john@example.com",
        "password": "securepassword123",
        "display_name": "User Two",
    }
    response2 = await async_client.post("/api/v1/auth/register", json=payload2)
    assert response2.status_code == 409
    assert "already in use" in response2.json()["detail"]


@pytest.mark.asyncio
async def test_register_validation_error(async_client: AsyncClient) -> None:
    """Test registering with invalid payloads returns 422 Unprocessable Entity."""
    payload = {
        "email": "invalid@example.com",
        "password": "short",
        "display_name": "Name",
    }
    response = await async_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_success(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test successful login sets HttpOnly cookie and resolves device."""
    settings = get_settings()

    # 1. Register first with mixed casing
    reg_payload = {
        "email": "Login_Success@Example.Com",
        "password": "password123",
        "display_name": "Login User",
    }
    await async_client.post("/api/v1/auth/register", json=reg_payload)

    # 2. Login with alternative casing
    login_payload = {
        "email": "login_success@example.com",
        "password": "password123",
        "device_identifier": "test-device-uuid-1",
        "device_name": "Simulator iPhone",
        "platform": "ios",
    }
    response = await async_client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 200
    assert response.json()["email"] == "login_success@example.com"

    # Verify session cookie was set with dynamic name from settings
    cookie_name = settings.SESSION_COOKIE_NAME
    assert cookie_name in response.cookies
    token = response.cookies.get(cookie_name)
    assert token is not None

    # Verify device and session exist in DB
    result = await db_session.execute(
        select(Device)
        .options(joinedload(Device.sessions))
        .where(Device.device_identifier == "test-device-uuid-1")
    )
    device = result.unique().scalar_one_or_none()
    assert device is not None
    assert device.name == "Simulator iPhone"
    assert len(device.sessions) == 1


@pytest.mark.asyncio
async def test_login_invalid_credentials(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test login with incorrect password returns 401 Unauthorized."""
    reg_payload = {
        "email": "login_invalid@example.com",
        "password": "password123",
        "display_name": "Login User",
    }
    await async_client.post("/api/v1/auth/register", json=reg_payload)

    login_payload = {
        "email": "login_invalid@example.com",
        "password": "wrongpassword",
        "device_identifier": "device-1",
        "platform": "web",
    }
    response = await async_client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_me_flow(async_client: AsyncClient, db_session: AsyncSession) -> None:
    """Test GET /auth/me returns profile for authenticated user, else 401."""
    response = await async_client.get("/api/v1/auth/me")
    assert response.status_code == 401

    email = "get_me@example.com"
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "display_name": "Me"},
    )
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "password123",
            "device_identifier": "device-me",
            "platform": "web",
        },
    )
    assert login_res.status_code == 200

    profile_res = await async_client.get("/api/v1/auth/me")
    assert profile_res.status_code == 200
    assert profile_res.json()["email"] == email


@pytest.mark.asyncio
async def test_logout_clears_cookie(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test POST /auth/logout revokes session in DB and deletes client cookie."""
    settings = get_settings()
    cookie_name = settings.SESSION_COOKIE_NAME

    email = "logout@example.com"
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "display_name": "Logout User"},
    )
    await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "password123",
            "device_identifier": "device-logout",
            "platform": "web",
        },
    )
    assert cookie_name in async_client.cookies

    # Logout
    logout_res = await async_client.post("/api/v1/auth/logout")
    assert logout_res.status_code == 204
    assert (
        cookie_name not in async_client.cookies
        or async_client.cookies[cookie_name] == ""
    )

    # Verify session deleted in DB
    result = await db_session.execute(select(UserSession))
    assert len(result.scalars().all()) == 0


@pytest.mark.asyncio
async def test_session_management(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test listing active sessions and revoking other/specific sessions."""
    email = "session_manage@example.com"
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "display_name": "User"},
    )

    async with (
        AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client_a,
        AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client_b,
    ):
        await client_a.post(
            "/api/v1/auth/login",
            json={
                "email": email,
                "password": "password123",
                "device_identifier": "device-a",
                "device_name": "Device A",
                "platform": "web",
            },
        )

        await client_b.post(
            "/api/v1/auth/login",
            json={
                "email": email,
                "password": "password123",
                "device_identifier": "device-b",
                "device_name": "Device B",
                "platform": "ios",
            },
        )

        # List sessions from Device B
        sessions_res = await client_b.get("/api/v1/auth/sessions")
        assert sessions_res.status_code == 200
        sessions_data = sessions_res.json()
        assert len(sessions_data) == 2

        # Verify current sessions are correctly flagged
        current_session = next(s for s in sessions_data if s["is_current"])
        other_session = next(s for s in sessions_data if not s["is_current"])

        assert current_session["device_name"] == "Device B"
        assert other_session["device_name"] == "Device A"

        # Revoke session A (other session) from Device B
        revoke_res = await client_b.delete(
            f"/api/v1/auth/sessions/{other_session['id']}"
        )
        assert revoke_res.status_code == 204

        # Verify session A is gone
        sessions_res2 = await client_b.get("/api/v1/auth/sessions")
        assert len(sessions_res2.json()) == 1

        # Device A should now be logged out
        me_res = await client_a.get("/api/v1/auth/me")
        assert me_res.status_code == 401


@pytest.mark.asyncio
async def test_device_centric_view(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test GET /auth/devices groups active sessions correctly under devices."""
    email = "device_view@example.com"
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "display_name": "User"},
    )

    async with (
        AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client_a,
        AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client_b,
    ):
        # Establish two sessions on Device A (e.g. Chrome and Firefox on same device_identifier)
        await client_a.post(
            "/api/v1/auth/login",
            json={
                "email": email,
                "password": "password123",
                "device_identifier": "device-shared",
                "device_name": "My Desktop",
                "platform": "web",
            },
        )
        await client_a.post(
            "/api/v1/auth/login",
            json={
                "email": email,
                "password": "password123",
                "device_identifier": "device-shared",
                "device_name": "My Desktop",
                "platform": "web",
            },
        )

        # Establish one session on Device B
        await client_b.post(
            "/api/v1/auth/login",
            json={
                "email": email,
                "password": "password123",
                "device_identifier": "device-mobile",
                "device_name": "My iPhone",
                "platform": "ios",
            },
        )

        # Query devices view from Device B
        devices_res = await client_b.get("/api/v1/auth/devices")
        assert devices_res.status_code == 200
        devices = devices_res.json()

        # Should list 2 devices
        assert len(devices) == 2

        # Device B is mobile, should be flagged as is_current
        mobile_device = next(d for d in devices if d["name"] == "My iPhone")
        assert mobile_device["is_current"] is True
        assert len(mobile_device["sessions"]) == 1
        assert mobile_device["sessions"][0]["is_current"] is True

        # Device A is shared desktop, should NOT be flagged as is_current
        desktop_device = next(d for d in devices if d["name"] == "My Desktop")
        assert desktop_device["is_current"] is False
        assert len(desktop_device["sessions"]) == 2
        # All sessions on Device A should be is_current=False when queried from Device B
        assert all(not s["is_current"] for s in desktop_device["sessions"])


@pytest.mark.asyncio
async def test_last_used_at_threshold_throttling(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test that session last_used_at write-back is throttled within 5 minutes."""
    email = "throttle@example.com"
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "display_name": "User"},
    )
    await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "password123",
            "device_identifier": "device-throttle",
            "platform": "web",
        },
    )

    # Initial request resolves session and caches last_used_at
    res1 = await async_client.get("/api/v1/auth/me")
    assert res1.status_code == 200

    # Query DB to get the current last_used_at
    result = await db_session.execute(select(UserSession))
    session = result.scalars().first()
    assert session is not None
    original_last_used = session.last_used_at

    # Second immediate request should NOT update last_used_at
    res2 = await async_client.get("/api/v1/auth/me")
    assert res2.status_code == 200

    db_session.expire_all()  # Clear identity map to read from DB
    result2 = await db_session.execute(select(UserSession))
    session2 = result2.scalars().first()
    assert session2 is not None
    assert session2.last_used_at == original_last_used  # Remains unchanged

    # Mock/update last_used_at in the DB to be older than 10 minutes ago
    session2.last_used_at = datetime.now(UTC) - timedelta(minutes=10)
    await db_session.flush()
    old_time = session2.last_used_at

    # Subsequent request should now trigger write-back update
    res3 = await async_client.get("/api/v1/auth/me")
    assert res3.status_code == 200

    db_session.expire_all()
    result3 = await db_session.execute(select(UserSession))
    session3 = result3.scalars().first()
    assert session3 is not None
    assert session3.last_used_at > old_time  # Successfully updated!
