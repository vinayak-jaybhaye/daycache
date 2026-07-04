"""Integration tests for the AI Summary features."""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import SummaryKind, SummaryScope
from app.db.models import User
from app.db.models.journal import Day, JournalEntry
from app.modules.ai.schemas import SummaryCreateInternal
from app.modules.ai.tasks import (
    generate_day_summary_task,
    generate_entry_summary_task,
    generate_monthly_summaries_task,
    generate_weekly_summaries_task,
)


@pytest.mark.asyncio
async def test_summary_create_internal_validation() -> None:
    """Test Pydantic validation rules for SummaryCreateInternal schema."""
    user_id = uuid4()
    entry_id = uuid4()
    day_id = uuid4()
    today = datetime.date.today()

    # 1. Valid entry scope
    entry_model = SummaryCreateInternal(
        user_id=user_id,
        scope=SummaryScope.ENTRY,
        journal_entry_id=entry_id,
    )
    assert entry_model.journal_entry_id == entry_id

    # 2. Invalid entry scope (missing journal_entry_id)
    with pytest.raises(ValidationError):
        SummaryCreateInternal(
            user_id=user_id,
            scope=SummaryScope.ENTRY,
        )

    # 3. Valid day scope
    day_model = SummaryCreateInternal(
        user_id=user_id,
        scope=SummaryScope.DAY,
        day_id=day_id,
    )
    assert day_model.day_id == day_id

    # 4. Invalid day scope (missing day_id)
    with pytest.raises(ValidationError):
        SummaryCreateInternal(
            user_id=user_id,
            scope=SummaryScope.DAY,
        )

    # 5. Valid week scope
    week_model = SummaryCreateInternal(
        user_id=user_id,
        scope=SummaryScope.WEEK,
        period_start=today,
        period_end=today,
    )
    assert week_model.period_start == today

    # 6. Invalid week scope (missing period dates)
    with pytest.raises(ValidationError):
        SummaryCreateInternal(
            user_id=user_id,
            scope=SummaryScope.WEEK,
        )


@pytest.mark.asyncio
async def test_ai_summary_endpoints_and_tasks(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test background task generation, retrieval, and 404 behavior."""
    # 1. Register and login User A
    user_email = "summaries_user@example.com"
    await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": user_email,
            "password": "password123",
            "display_name": "Summary Owner",
        },
    )
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": user_email,
            "password": "password123",
            "installation_id": "summaries-device",
            "platform": "web",
        },
    )
    assert login_res.status_code == 200

    # Fetch User ID from DB
    stmt = select(User).where(User.email == user_email)
    res = await db_session.execute(stmt)
    user = res.scalar_one()

    # 2. Assert 404 for missing summaries
    random_id = uuid4()
    res_404 = await async_client.get(f"/api/v1/ai/summaries/entry/{random_id}")
    assert res_404.status_code == 404

    # 3. Create entry in DB
    day = Day(user_id=str(user.id), date=datetime.date.today())
    db_session.add(day)
    await db_session.flush()

    entry = JournalEntry(
        day_id=str(day.id),
        title="First day reflection",
        content={
            "text": "I started writing a diary today. It felt really great and motivational."
        },
        content_text="I started writing a diary today. It felt really great and motivational.",
        word_count=10,
    )
    db_session.add(entry)

    # Create entry for weekly summary (last week's Monday)
    last_monday = datetime.date.today() - datetime.timedelta(
        days=datetime.date.today().weekday() + 7
    )
    day_week = Day(user_id=str(user.id), date=last_monday)
    db_session.add(day_week)
    await db_session.flush()
    entry_week = JournalEntry(
        day_id=str(day_week.id),
        title="Week reflection",
        content={"text": "Weekly reflection notes."},
        content_text="Weekly reflection notes.",
        word_count=3,
    )
    db_session.add(entry_week)

    # Create entry for monthly summary (previous month's 1st day)
    prev_month_start = (
        datetime.date.today().replace(day=1) - datetime.timedelta(days=1)
    ).replace(day=1)
    day_month = Day(user_id=str(user.id), date=prev_month_start)
    db_session.add(day_month)
    await db_session.flush()
    entry_month = JournalEntry(
        day_id=str(day_month.id),
        title="Month reflection",
        content={"text": "Monthly reflection notes."},
        content_text="Monthly reflection notes.",
        word_count=3,
    )
    db_session.add(entry_month)

    await db_session.flush()

    # 4. Trigger entry background task manually using context dictionary
    ctx = {"db": db_session}
    with patch.object(db_session, "commit", new=AsyncMock()):
        await generate_entry_summary_task(ctx, str(entry.id))

    # Fetch entry summary from API
    entry_summary_res = await async_client.get(f"/api/v1/ai/summaries/entry/{entry.id}")
    assert entry_summary_res.status_code == 200
    summary_data = entry_summary_res.json()
    assert summary_data["content"].startswith("Mock summary")
    assert "productivity" in summary_data["themes"]
    assert summary_data["scope"] == "entry"

    # 5. Trigger daily background task manually
    with patch.object(db_session, "commit", new=AsyncMock()):
        await generate_day_summary_task(ctx, str(day.id))

    # Fetch day summary from API
    day_summary_res = await async_client.get(f"/api/v1/ai/summaries/day/{day.date}")
    assert day_summary_res.status_code == 200
    assert day_summary_res.json()["scope"] == "day"

    # 6. Trigger scheduled weekly task manually
    with patch.object(db_session, "commit", new=AsyncMock()):
        await generate_weekly_summaries_task(ctx)
    last_monday = datetime.date.today() - datetime.timedelta(
        days=datetime.date.today().weekday() + 7
    )

    # Fetch weekly summary from API
    week_summary_res = await async_client.get(
        f"/api/v1/ai/summaries/week/{last_monday}"
    )
    assert week_summary_res.status_code == 200
    assert week_summary_res.json()["scope"] == "week"

    # 7. Trigger scheduled monthly task manually
    with patch.object(db_session, "commit", new=AsyncMock()):
        await generate_monthly_summaries_task(ctx)
    prev_month_start = (
        datetime.date.today().replace(day=1) - datetime.timedelta(days=1)
    ).replace(day=1)

    # Fetch monthly summary from API
    month_summary_res = await async_client.get(
        f"/api/v1/ai/summaries/month/{prev_month_start.year}/{prev_month_start.month}"
    )
    assert month_summary_res.status_code == 200
    assert month_summary_res.json()["scope"] == "month"


@pytest.mark.asyncio
async def test_ai_summary_tenant_isolation(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test that User B cannot retrieve or access User A's summaries."""
    # 1. Register and login User A
    user_a_email = "user_a_summary@example.com"
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

    stmt = select(User).where(User.email == user_a_email)
    res = await db_session.execute(stmt)
    user_a = res.scalar_one()

    # Create entry and summary for User A
    day_a = Day(user_id=str(user_a.id), date=datetime.date.today())
    db_session.add(day_a)
    await db_session.flush()

    entry_a = JournalEntry(
        day_id=str(day_a.id),
        title="User A reflections",
        content={"text": "I had a productive coding session."},
        content_text="I had a productive coding session.",
        word_count=5,
    )
    db_session.add(entry_a)
    await db_session.flush()

    ctx = {"db": db_session}
    with patch.object(db_session, "commit", new=AsyncMock()):
        await generate_entry_summary_task(ctx, str(entry_a.id))

    # 2. Register and login User B
    user_b_email = "user_b_summary@example.com"
    await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": user_b_email,
            "password": "password123",
            "display_name": "User B",
        },
    )
    await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": user_b_email,
            "password": "password123",
            "installation_id": "device-b",
            "platform": "web",
        },
    )

    # 3. Try to access User A's entry summary as User B
    access_res = await async_client.get(f"/api/v1/ai/summaries/entry/{entry_a.id}")
    assert access_res.status_code == 404


@pytest.mark.asyncio
async def test_hierarchical_summary_dependency_chain(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test that weekly, monthly, and yearly summaries recursively resolve lower level summaries on-demand."""
    # 1. Register and login User
    user_email = "hierarchy_user@example.com"
    await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": user_email,
            "password": "password123",
            "display_name": "Hierarchy Owner",
        },
    )
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": user_email,
            "password": "password123",
            "installation_id": "hierarchy-device",
            "platform": "web",
        },
    )
    assert login_res.status_code == 200

    # Fetch User ID from DB
    stmt = select(User).where(User.email == user_email)
    res = await db_session.execute(stmt)
    user = res.scalar_one()

    # Create entries for two days in the same week (e.g. 2025-07-07 Monday and 2025-07-08 Tuesday)
    day_1_date = datetime.date(2025, 7, 7)
    day_2_date = datetime.date(2025, 7, 8)

    day1 = Day(user_id=str(user.id), date=day_1_date)
    day2 = Day(user_id=str(user.id), date=day_2_date)
    db_session.add_all([day1, day2])
    await db_session.flush()

    entry1 = JournalEntry(
        day_id=str(day1.id),
        title="Day 1 reflection",
        content={"text": "Today I built a custom API."},
        content_text="Today I built a custom API.",
        word_count=6,
    )
    entry2 = JournalEntry(
        day_id=str(day2.id),
        title="Day 2 reflection",
        content={"text": "Today I optimized queries."},
        content_text="Today I optimized queries.",
        word_count=5,
    )
    db_session.add_all([entry1, entry2])
    await db_session.flush()

    # Now, let's trigger the weekly summary generation for that week.
    # Note: we haven't generated day summaries for day1 and day2 yet.
    # The week starts on Monday, 2025-07-07.

    # We will mock the LLM generator so we can inspect the generated prompts.
    from app.services.llm.provider import MockLLMProvider

    original_generate = MockLLMProvider.generate
    captured_prompts = []

    from typing import Any

    async def mock_generate(self: Any, prompt: str, response_model: Any) -> Any:
        captured_prompts.append(prompt)
        return await original_generate(self, prompt, response_model)

    with patch.object(MockLLMProvider, "generate", mock_generate):
        # We call the weekly summary endpoint to generate it
        week_res = await async_client.get("/api/v1/ai/summaries/week/2025-07-07")
        assert week_res.status_code == 200

    # Let's inspect what happened:
    # 1. Day summaries for 2025-07-07 and 2025-07-08 should have been generated.
    from app.db.repositories.summary import SummaryRepository

    summary_repo = SummaryRepository(db_session)
    day_1_summary = await summary_repo.get_latest(
        user_id=user.id,
        scope=SummaryScope.DAY,
        kind=SummaryKind.SUMMARY,
        day_id=day1.id,
    )
    day_2_summary = await summary_repo.get_latest(
        user_id=user.id,
        scope=SummaryScope.DAY,
        kind=SummaryKind.SUMMARY,
        day_id=day2.id,
    )
    assert day_1_summary is not None
    assert day_2_summary is not None

    # 2. We should have captured three generate calls: two for the days, one for the week.
    assert len(captured_prompts) == 3
    # The last prompt should be the week summary prompt and contain the text of daily summaries.
    week_prompt = captured_prompts[-1]
    assert "Daily Summary for 2025-07-07:" in week_prompt
    assert "Daily Summary for 2025-07-08:" in week_prompt

    # 3. Request the weekly summary using a non-Monday date (e.g. Wednesday 2025-07-09)
    # It should automatically resolve to the same week starting on Monday 2025-07-07 and hit the cache.
    with patch.object(MockLLMProvider, "generate", mock_generate):
        week_res_wed = await async_client.get("/api/v1/ai/summaries/week/2025-07-09")
        assert week_res_wed.status_code == 200
        # The returned summary should have period_start matching Monday 2025-07-07
        assert week_res_wed.json()["period_start"] == "2025-07-07"

    # 4. Confirm no extra LLM generator call was made for this Wednesday request (cached hit)
    assert len(captured_prompts) == 3

    # 5. Request the yearly summary for 2025 on-the-fly (past year, generation allowed).
    # This should recursively generate Month (July 2025) and Year summaries.
    captured_prompts.clear()
    with patch.object(MockLLMProvider, "generate", mock_generate):
        year_res = await async_client.get("/api/v1/ai/summaries/year/2025")
        assert year_res.status_code == 200
        assert year_res.json()["scope"] == "year"
        assert year_res.json()["period_start"] == "2025-01-01"

    # Confirm we generated Month (July) and Year summaries (2 new calls)
    assert len(captured_prompts) == 2
    # Verify the yearly prompt contained the monthly summary
    year_prompt = captured_prompts[-1]
    assert "Monthly Summary for July 2025:" in year_prompt

    # 6. Request the yearly summary for the current year (2026).
    # Since it is ongoing and no summary is pre-generated, it should return 404 with a nice message.
    # First, let's create a day and entry in 2026 so that it passes the entries range check.
    current_year = datetime.date.today().year
    day_curr = Day(user_id=str(user.id), date=datetime.date(current_year, 1, 1))
    db_session.add(day_curr)
    await db_session.flush()

    entry_curr = JournalEntry(
        day_id=str(day_curr.id),
        title="New Year",
        content={"text": "Starting the current year reflection."},
        content_text="Starting the current year reflection.",
        word_count=5,
    )
    db_session.add(entry_curr)
    await db_session.flush()

    curr_year_res = await async_client.get(f"/api/v1/ai/summaries/year/{current_year}")
    assert curr_year_res.status_code == 404
    assert "still ongoing" in curr_year_res.json()["detail"]
    assert "Keep journaling" in curr_year_res.json()["detail"]


def test_summary_output_healing_keys() -> None:
    """Test that SummaryOutput schema heals casing and list variations from LLM response."""
    from app.modules.ai.schemas import SummaryOutput

    # Case A: Title case keys and single strings instead of lists
    data_a = {
        "Summary": "This was a good day overall.",
        "Highlights": "Finished project tasks.",
        "Challenges": None,
        "Themes": ["work", "productivity"],
    }
    obj_a = SummaryOutput.model_validate(data_a)
    assert obj_a.content == "This was a good day overall."
    assert obj_a.highlights == ["Finished project tasks."]
    assert obj_a.challenges == []
    assert obj_a.themes == ["work", "productivity"]

    # Case B: Completely missing keys and custom content key
    data_b = {
        "some_long_text_key": "This is the actual summary text generated by the model.",
    }
    obj_b = SummaryOutput.model_validate(data_b)
    assert obj_b.content == "This is the actual summary text generated by the model."
    assert obj_b.highlights == []
    assert obj_b.challenges == []
    assert obj_b.themes == []
