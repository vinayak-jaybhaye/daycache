"""Smoke tests for the health and readiness endpoints."""

from __future__ import annotations

from httpx import AsyncClient


async def test_health_returns_200(async_client: AsyncClient) -> None:
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "env" in data


async def test_health_response_includes_request_id(async_client: AsyncClient) -> None:
    response = await async_client.get("/api/v1/health")
    assert "x-request-id" in response.headers


async def test_health_accepts_incoming_request_id(async_client: AsyncClient) -> None:
    custom_id = "my-trace-id-1234"
    response = await async_client.get(
        "/api/v1/health", headers={"X-Request-ID": custom_id}
    )
    assert response.headers["x-request-id"] == custom_id


async def test_ready_returns_503_without_db(async_client: AsyncClient) -> None:
    """Without a real database the readiness check must return 503."""
    response = await async_client.get("/api/v1/ready")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "unavailable"
    assert data["checks"]["database"] == "error"


async def test_not_found_returns_consistent_envelope(
    async_client: AsyncClient,
) -> None:
    response = await async_client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert "detail" in data
    assert "request_id" in data
