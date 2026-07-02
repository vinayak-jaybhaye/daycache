"""API v1 router.

Collects all v1 feature sub-routers.
Uncomment each router as the corresponding feature module is implemented.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.health import router as health_router

# from app.api.v1.auth import router as auth_router
# from app.api.v1.journal import router as journal_router
# from app.api.v1.media import router as media_router
# from app.api.v1.search import router as search_router
# from app.api.v1.ai import router as ai_router

router = APIRouter()

router.include_router(health_router, tags=["health"])

# router.include_router(auth_router, prefix="/auth", tags=["auth"])
# router.include_router(journal_router, prefix="/journal", tags=["journal"])
# router.include_router(media_router, prefix="/media", tags=["media"])
# router.include_router(search_router, prefix="/search", tags=["search"])
# router.include_router(ai_router, prefix="/ai", tags=["ai"])
