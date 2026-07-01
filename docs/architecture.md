# Architecture

## Overview

DayCache is a monorepo containing a Next.js frontend, a FastAPI backend, and shared infrastructure configuration.

```
┌──────────────────────────────────────────────────────────┐
│                        Browser                           │
│                   Next.js (apps/web)                     │
└──────────────────────┬───────────────────────────────────┘
                       │ HTTP / REST
┌──────────────────────▼───────────────────────────────────┐
│                  FastAPI (apps/api)                       │
│  ┌───────────┐  ┌───────────┐  ┌──────────────────────┐  │
│  │  modules/ │  │  core/    │  │  middleware/          │  │
│  │  auth     │  │  config   │  │  cors, auth, logging  │  │
│  │  journal  │  │  security │  └──────────────────────┘  │
│  │  media    │  └───────────┘                            │
│  │  search   │                                           │
│  │  ai       │                                           │
│  └───────────┘                                           │
└───────────┬──────────────────────────────────────────────┘
            │
    ┌───────┴────────┐
    │                │
┌───▼────┐     ┌─────▼──┐
│Postgres│     │ Redis  │
└────────┘     └────────┘
```

## Frontend (`apps/web`)

Next.js App Router application organized by feature.

```
apps/web/
├── app/              Next.js route segments (layout, page, loading, error)
├── components/       Shared, reusable UI primitives (Button, Input, Modal…)
├── features/         Domain feature modules (each mirrors an API module)
│   ├── auth/
│   ├── journal/
│   └── …
├── hooks/            Custom React hooks (useAuth, useJournal…)
├── lib/              API client, utility functions, constants
├── providers/        React context providers (AuthProvider, ThemeProvider…)
├── styles/           Global CSS, design tokens
└── types/            Global TypeScript type declarations
```

**Key decisions:**
- Feature-based, not layer-based. All auth UI lives in `features/auth/`.
- `components/` holds only generic, reusable primitives — no business logic.
- API calls are centralized in `lib/api/` using a typed fetch wrapper.

## Backend (`apps/api`)

FastAPI application organized around domain modules.

```
apps/api/app/
├── core/             Configuration, security utilities, dependencies
├── db/               Database session factory, base model
├── middleware/       Custom ASGI middleware
├── modules/          Feature modules (each is self-contained)
│   ├── auth/         router.py, service.py, repository.py, schemas.py
│   ├── journal/
│   ├── media/
│   ├── search/
│   └── ai/
└── storage/          File/object storage abstraction
```

**Key decisions:**
- Each module owns its router, service, repository, and Pydantic schemas.
- Routers never access the database directly — they call services.
- Services never import SQLAlchemy models directly — they use repositories.
- `core/` contains shared concerns (config, JWT helpers, dependency injection).

## Infrastructure

Local development runs on Docker Compose (`infra/docker-compose.yml`):
- **PostgreSQL 16** — primary database
- **Redis 7** — caching and future task queues

Production infrastructure is defined separately (see [Deployment](deployment.md)).

## Data Flow

```
Request → Middleware → Router → Service → Repository → Database
                        ↓
                    Schemas (validate in, serialize out)
```

1. Middleware authenticates the JWT and injects the user.
2. Router parses and validates the request body via Pydantic schemas.
3. Service implements business logic, calling one or more repositories.
4. Repository executes SQL queries via SQLAlchemy async session.
5. Response is serialized back through Pydantic response schemas.
