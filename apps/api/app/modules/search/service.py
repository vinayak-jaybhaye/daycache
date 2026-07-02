"""Search service.

Contains all business logic for the search feature.

Rules:
- No FastAPI imports (APIRouter, Request, Response, Depends, HTTPException).
- No direct SQLAlchemy access — use repositories only.
- No imports from other feature modules.
"""

from __future__ import annotations
