"""Reflect API router."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from app.api.deps import get_arq_pool, get_current_user, get_db
from app.db.models import User
from app.db.repositories.reflect import ReflectRepository
from app.modules.reflect.schemas import (
    ReflectMessageCreate,
    ReflectMessageResponse,
)
from app.modules.reflect.service import ReflectService

if TYPE_CHECKING:
    from arq import ArqRedis
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get(
    "/messages",
    response_model=list[ReflectMessageResponse],
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
)
async def get_messages(
    date_val: date | None = Query(
        None, alias="date", description="Filter by calendar date"
    ),
    before: datetime | None = Query(
        None, description="TIMESTAMPTZ cursor for pagination"
    ),
    limit: int = Query(50, ge=1, le=100, description="Items limit"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ReflectMessageResponse]:
    """Retrieve message history for the authenticated user's Reflect session."""
    reflect_repo = ReflectRepository(db)
    session = await reflect_repo.get_session_by_user_id(current_user.id)
    if session is None:
        # Transparently return empty list if no session exists yet
        return []

    messages = await reflect_repo.get_session_history(
        session_id=session.id,
        before=before,
        date_filter=date_val,
        limit=limit,
    )
    return [ReflectMessageResponse.model_validate(m) for m in messages]


@router.get(
    "/today",
    response_model=list[ReflectMessageResponse],
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
)
async def get_today_messages(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ReflectMessageResponse]:
    """Retrieve today's messages in the user's Reflect session, returning 404 if none exist."""
    reflect_repo = ReflectRepository(db)
    session = await reflect_repo.get_session_by_user_id(current_user.id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reflect session not found.",
        )

    messages = await reflect_repo.get_session_history(
        session_id=session.id,
        date_filter=datetime.now(UTC).date(),
        limit=100,
    )
    if not messages:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Reflect messages found for today.",
        )

    return [ReflectMessageResponse.model_validate(m) for m in messages]


@router.post(
    "/messages",
    status_code=status.HTTP_200_OK,
)
async def send_message(
    data: ReflectMessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis = Depends(get_arq_pool),
) -> StreamingResponse:
    """Send a message to Reflect and stream a warm response via SSE."""
    service = ReflectService(db)
    event_stream = await service.handle_message_pipeline(
        user_id=current_user.id,
        content=data.content,
        arq_pool=arq_pool,
    )
    return StreamingResponse(
        event_stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
