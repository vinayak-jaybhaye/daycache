"""Search API router."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.db.models import User
from app.modules.search.schemas import SearchResultItem
from app.modules.search.service import SearchService

router = APIRouter()


@router.get("", response_model=list[SearchResultItem])
async def search_entries(
    q: str = Query(..., description="The query string to search for"),
    mode: Literal["instant", "semantic", "hybrid"] = Query(
        "hybrid", description="Search mode to execute"
    ),
    limit: int = Query(20, ge=1, le=100, description="Max results limit"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SearchResultItem]:
    """Perform a hybrid, lexical, or semantic search over journal entries."""
    return await SearchService.search_entries(
        db=db,
        user_id=current_user.id,
        query=q,
        mode=mode,
        limit=limit,
    )
