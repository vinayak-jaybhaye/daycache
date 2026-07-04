from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UserSettings
from app.db.models.journal import Day, JournalEntry
from app.modules.journal.schemas import JournalEntryResponse
from app.modules.search.schemas import SearchResultItem
from app.services.llm.personas import VALID_PERSONA_NAMES, get_persona


def test_get_persona_defensive():
    """get_persona() returns default for unrecognized name (defensive)"""
    default_p = get_persona("Mira")
    unrecognized_p = get_persona("InvalidName")
    assert unrecognized_p == default_p
    assert unrecognized_p.name == "Mira"


@pytest.mark.asyncio
async def test_get_personas_endpoint(async_client: AsyncClient):
    """GET /personas returns all 6 personas with name and tagline and requires no auth."""
    response = await async_client.get("/api/v1/personas")
    assert response.status_code == 200
    data = response.json()
    assert "personas" in data
    assert "default" in data
    assert data["default"] == "Mira"
    assert len(data["personas"]) == 6

    names = {p["name"] for p in data["personas"]}
    assert names == VALID_PERSONA_NAMES

    # Ensure tagline is included for all
    for p in data["personas"]:
        assert "tagline" in p
        assert len(p["tagline"]) > 0


@pytest.mark.asyncio
async def test_update_settings_validation(
    async_client: AsyncClient, db_session: AsyncSession
):
    """PATCH settings validates persona name successfully and returns 422 for invalid."""
    # Register and login helper
    from tests.test_recall import register_and_login

    await register_and_login(async_client, "persona_val@example.com")

    # Verify default is Mira
    get_res = await async_client.get("/api/v1/users/me/settings")
    assert get_res.status_code == 200
    assert get_res.json()["ai_persona_name"] == "Mira"

    # PATCH with valid name
    patch_res = await async_client.patch(
        "/api/v1/users/me/settings",
        json={"ai_persona_name": "Sage"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["ai_persona_name"] == "Sage"

    # PATCH settings via /api/v1/settings directly (alias)
    patch_res_alias = await async_client.patch(
        "/api/v1/settings",
        json={"ai_persona_name": "Echo"},
    )
    assert patch_res_alias.status_code == 200
    assert patch_res_alias.json()["ai_persona_name"] == "Echo"

    # PATCH with invalid name returns 422
    invalid_patch = await async_client.patch(
        "/api/v1/users/me/settings",
        json={"ai_persona_name": "InvalidName"},
    )
    assert invalid_patch.status_code == 422


@pytest.mark.asyncio
async def test_default_persona_on_onboarding_skip(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Default persona is Mira when user skips onboarding (new registration default)."""
    # Trigger user registration
    reg_response = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "skip_onboard@example.com",
            "password": "password123",
            "display_name": "Skip Onboard",
        },
    )
    assert reg_response.status_code == 201
    user_id = reg_response.json()["id"]

    # Check database defaults directly
    stmt = select(UserSettings).where(UserSettings.user_id == user_id)
    res = await db_session.execute(stmt)
    settings = res.scalar_one_or_none()
    assert settings is not None
    assert settings.ai_persona_name == "Mira"


@pytest.mark.asyncio
async def test_recall_and_reflect_prompt_injection(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Recall and Reflect system prompts contain persona name and personality block, updating immediately."""
    from tests.test_recall import register_and_login

    user_info = await register_and_login(async_client, "prompt_test@example.com")
    user_uuid = user_info["id"]

    # --- Recall Integration ---
    # Setup database day & entry for search results
    day = Day(user_id=user_uuid, date=date(2026, 7, 4))
    db_session.add(day)
    await db_session.flush()

    entry = JournalEntry(
        day_id=day.id,
        title="Test Entry",
        content={"text": "Today I went to the park and met a friend."},
        content_text="Today I went to the park and met a friend.",
        word_count=10,
        tags=[],
        moods=[],
    )
    db_session.add(entry)
    await db_session.flush()

    mock_results = [
        SearchResultItem(
            entry=JournalEntryResponse.model_validate(entry),
            score=0.95,
            match_type="hybrid",
            highlight_snippet="Today I went to the park and met a friend.",
            day_date=day.date,
        )
    ]

    captured_recall_prompts = []

    async def mock_recall_stream(prompt: str, *args: object, **kwargs: object):
        captured_recall_prompts.append(prompt)
        yield "Recall answer."

    mock_provider = MagicMock()
    mock_provider.stream = mock_recall_stream

    # Default persona is Mira. Send message and check prompt contains Mira.
    from app.modules.search.service import SearchService

    with (
        patch.object(SearchService, "search", AsyncMock(return_value=mock_results)),
        patch(
            "app.modules.recall.service.get_llm_provider", return_value=mock_provider
        ),
    ):
        async with async_client.stream(
            "POST",
            "/api/v1/recall/messages",
            json={"content": "Recall what happened at the park?"},
        ) as res:
            assert res.status_code == 200

    assert len(captured_recall_prompts) == 1
    prompt = captured_recall_prompts[0]
    assert "You are Mira" in prompt
    assert "warm, gentle, and deeply empathetic" in prompt

    # Update persona to Sage
    await async_client.patch(
        "/api/v1/users/me/settings",
        json={"ai_persona_name": "Sage"},
    )

    # Send second message and check prompt contains Sage immediately
    captured_recall_prompts.clear()
    with (
        patch.object(SearchService, "search", AsyncMock(return_value=mock_results)),
        patch(
            "app.modules.recall.service.get_llm_provider", return_value=mock_provider
        ),
    ):
        async with async_client.stream(
            "POST",
            "/api/v1/recall/messages",
            json={"content": "Recall what happened at the park?"},
        ) as res:
            assert res.status_code == 200

    assert len(captured_recall_prompts) == 1
    prompt = captured_recall_prompts[0]
    assert "You are Sage" in prompt
    assert "calm, thoughtful, and philosophical" in prompt

    # --- Reflect Integration ---
    captured_reflect_prompts = []

    async def mock_reflect_stream(prompt: str, *args: object, **kwargs: object):
        captured_reflect_prompts.append(prompt)
        yield "Reflect answer."

    mock_provider_reflect = MagicMock()
    mock_provider_reflect.stream = mock_reflect_stream

    # Currently persona is Sage. Send message to Reflect.
    with patch(
        "app.modules.reflect.service.get_llm_provider",
        return_value=mock_provider_reflect,
    ):
        async with async_client.stream(
            "POST",
            "/api/v1/reflect/messages",
            json={"content": "I had a great day today!"},
        ) as res:
            assert res.status_code == 200

    assert len(captured_reflect_prompts) == 1
    prompt = captured_reflect_prompts[0]
    assert "You are Sage" in prompt
    assert "calm, thoughtful, and philosophical" in prompt

    # Change persona back to Echo
    await async_client.patch(
        "/api/v1/users/me/settings",
        json={"ai_persona_name": "Echo"},
    )

    captured_reflect_prompts.clear()
    with patch(
        "app.modules.reflect.service.get_llm_provider",
        return_value=mock_provider_reflect,
    ):
        async with async_client.stream(
            "POST",
            "/api/v1/reflect/messages",
            json={"content": "Another busy day!"},
        ) as res:
            assert res.status_code == 200

    assert len(captured_reflect_prompts) == 1
    prompt = captured_reflect_prompts[0]
    assert "You are Echo" in prompt
    assert "curious, playful, and genuinely enthusiastic" in prompt
