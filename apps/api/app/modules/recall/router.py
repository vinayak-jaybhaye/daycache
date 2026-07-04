"""Recall API router."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from app.api.deps import get_current_user, get_db
from app.db.models import User
from app.db.repositories.recall import RecallRepository
from app.modules.recall.schemas import (
    MessageCreate,
    RecallMessageResponse,
    RecallSessionResponse,
)
from app.modules.recall.service import RecallService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get(
    "/session",
    response_model=RecallSessionResponse,
    status_code=status.HTTP_200_OK,
)
async def get_session(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RecallSessionResponse:
    """Retrieve the Recall session metadata for the authenticated user."""
    recall_repo = RecallRepository(db)
    session = await recall_repo.get_session_by_user_id(current_user.id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recall session not found.",
        )
    return RecallSessionResponse.model_validate(session)


@router.get(
    "/messages",
    response_model=list[RecallMessageResponse],
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
) -> list[RecallMessageResponse]:
    """Retrieve message history for the authenticated user's session, optionally filtered and paginated."""
    recall_repo = RecallRepository(db)
    session = await recall_repo.get_session_by_user_id(current_user.id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recall session not found.",
        )

    messages = await recall_repo.get_session_history(
        session_id=session.id,
        before=before,
        date_filter=date_val,
        limit=limit,
    )
    return [RecallMessageResponse.model_validate(m) for m in messages]


@router.post(
    "/messages",
    status_code=status.HTTP_200_OK,
)
async def send_message(
    data: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Send a query to Recall and stream a grounded response via SSE."""
    service = RecallService(db)
    event_stream = await service.handle_message_pipeline(
        user_id=current_user.id,
        content=data.content,
    )
    return StreamingResponse(
        event_stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.delete(
    "/messages/{message_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_message(
    message_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Hard delete a single message belonging to the user.

    If a user message is deleted, its following assistant response turn is also deleted.
    """
    recall_repo = RecallRepository(db)
    success = await recall_repo.delete_paired_messages(message_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found.",
        )


@router.delete(
    "/messages",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_messages_by_date(
    date_val: date | None = Query(
        None, alias="date", description="Target calendar date to clear"
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Hard delete all messages for a given calendar day in the user's session."""
    if date_val is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Date query parameter is required.",
        )

    recall_repo = RecallRepository(db)
    session = await recall_repo.get_session_by_user_id(current_user.id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recall session not found.",
        )

    await recall_repo.delete_messages_by_date(session.id, date_val)
