from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialise DB connections, caches, etc.
    yield
    # Shutdown: clean up resources.


app = FastAPI(
    title="DayCache API",
    version="0.1.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers (uncomment as modules are implemented)
# ---------------------------------------------------------------------------

# from app.modules.auth.router import router as auth_router
# from app.modules.journal.router import router as journal_router
# from app.modules.media.router import router as media_router
# from app.modules.search.router import router as search_router
# from app.modules.ai.router import router as ai_router

# app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
# app.include_router(journal_router, prefix="/api/v1/journal", tags=["journal"])
# app.include_router(media_router, prefix="/api/v1/media", tags=["media"])
# app.include_router(search_router, prefix="/api/v1/search", tags=["search"])
# app.include_router(ai_router, prefix="/api/v1/ai", tags=["ai"])


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
