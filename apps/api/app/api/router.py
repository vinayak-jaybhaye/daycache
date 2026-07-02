"""Root API router.

Mounts all versioned sub-routers.
Add new API versions here as they are introduced.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.router import router as v1_router
from app.core.constants import API_V1_PREFIX

router = APIRouter()
router.include_router(v1_router, prefix=API_V1_PREFIX)
