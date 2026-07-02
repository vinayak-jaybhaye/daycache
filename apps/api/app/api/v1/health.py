"""Health and readiness endpoints.

GET /api/v1/health  — liveness probe (no I/O, always fast)
GET /api/v1/ready   — readiness probe (checks infrastructure dependencies)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import Settings, get_settings

router = APIRouter()


@router.get(
    "/health",
    summary="Liveness check",
    description="Returns immediately. Used by load balancers to verify the process is alive.",
)
async def health(
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    """Return application liveness status."""
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "env": settings.APP_ENV,
    }


@router.get(
    "/ready",
    summary="Readiness check",
    description=(
        "Verifies infrastructure dependencies. "
        "Returns 200 only when all critical services are reachable."
    ),
)
async def ready(
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Check readiness of infrastructure dependencies.

    Current checks:
    - PostgreSQL: executes ``SELECT 1``

    Future checks (not yet implemented):
    - Redis connectivity
    - Configured storage backend reachability
    """
    checks: dict[str, str] = {}

    # --- PostgreSQL -------------------------------------------------------
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"

    # Determine overall status.
    all_ok = all(v == "ok" for v in checks.values())
    http_status = status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=http_status,
        content={
            "status": "ready" if all_ok else "unavailable",
            "checks": checks,
        },
    )
