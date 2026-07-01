# DayCache

AI-powered journaling. A modern, privacy-first alternative to Day One.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS v4 |
| Backend | FastAPI, SQLAlchemy (async), Alembic, Pydantic v2 |
| Database | PostgreSQL 16 |
| Cache / Queue | Redis 7 |
| Python tooling | uv, ruff, pyright, pytest |
| JS tooling | pnpm, ESLint, Prettier, tsc |
| Infrastructure | Docker Compose |
| CI | GitHub Actions |

## Repository Structure

```
daycache/
├── apps/
│   ├── web/        Next.js frontend
│   ├── api/        FastAPI backend
│   └── mobile/     React Native (future placeholder)
├── docs/           Architecture docs, ADRs, guidelines
├── infra/          Docker Compose, Postgres, Redis configs
├── .github/        GitHub Actions CI workflows
├── Makefile        Developer command shortcuts
├── pyproject.toml  uv workspace root
└── pnpm-workspace.yaml  pnpm workspace root
```

## Quick Start

```bash
# 1. Install all dependencies and git hooks
make setup

# 2. Start local infrastructure (Postgres + Redis)
make dev.infra

# 3. Run database migrations
make db.migrate

# 4. Start the API and web servers (each in a separate terminal)
make dev.api
make dev.web
```

The web app is available at **http://localhost:3000** and the API at **http://localhost:8000**.

## Common Commands

| Command | Description |
|---|---|
| `make setup` | Install deps + git hooks |
| `make dev.web` | Next.js dev server |
| `make dev.api` | FastAPI dev server |
| `make dev.infra` | Start Postgres + Redis |
| `make lint` | Lint all code |
| `make format` | Auto-format all code |
| `make type-check` | Run Pyright + tsc |
| `make test` | Run all tests |
| `make check` | Full CI check locally |
| `make db.migrate` | Apply migrations |
| `make db.rollback` | Roll back last migration |
| `make reset` | Wipe local env and restart |

Run `make help` for the complete list.

## Documentation

- [Local Development](docs/local-development.md)
- [Architecture](docs/architecture.md)
- [API Conventions](docs/api-conventions.md)
- [Database Design](docs/database.md)
- [Coding Guidelines](docs/coding-guidelines.md)
- [Deployment](docs/deployment.md)
- [Architecture Decision Records](docs/adr/)
