"""API v1 router.

Collects all v1 feature sub-routers.
Uncomment each router as the corresponding feature module is implemented.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.ai import router as ai_router
from app.api.v1.auth import router as auth_router
from app.api.v1.collections import router as collections_router
from app.api.v1.health import router as health_router
from app.api.v1.journal import days_router, entries_router, moods_router
from app.api.v1.search import router as search_router

# from app.api.v1.media import router as media_router  # unmounted — media is internal infrastructure
from app.api.v1.settings import router as settings_router
from app.api.v1.tags import router as tags_router
from app.api.v1.users import router as users_router

router = APIRouter()

router.include_router(health_router, tags=["health"])

router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(users_router, prefix="/users", tags=["users"])
router.include_router(settings_router, prefix="/settings", tags=["settings"])
router.include_router(tags_router, prefix="/tags", tags=["tags"])
router.include_router(collections_router, prefix="/collections", tags=["collections"])
router.include_router(entries_router, prefix="/entries", tags=["entries"])
router.include_router(days_router, prefix="/days", tags=["days"])
router.include_router(moods_router, prefix="/moods", tags=["moods"])
# router.include_router(media_router, prefix="/media", tags=["media"])  # unmounted
router.include_router(search_router, prefix="/search", tags=["search"])
router.include_router(ai_router, prefix="/ai/summaries", tags=["ai"])
