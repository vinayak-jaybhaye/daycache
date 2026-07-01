# Local Development

This guide walks you through setting up a complete local development environment for DayCache.

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| Node.js | ≥ 22 | [nvm](https://github.com/nvm-sh/nvm) |
| pnpm | ≥ 9 | `npm i -g pnpm` |
| Python | ≥ 3.12 | [pyenv](https://github.com/pyenv/pyenv) |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Docker | latest | [Docker Desktop](https://www.docker.com/products/docker-desktop/) |
| pre-commit | latest | `uv tool install pre-commit` |

## Initial Setup

```bash
# Clone the repository
git clone <repo-url>
cd daycache

# Install all dependencies and register git hooks
make setup
```

`make setup` runs:
1. `pnpm install` — JS/TS dependencies (single root node_modules)
2. `uv sync` — Python dependencies
3. `pre-commit install` — installs git hooks

## Environment Variables

Copy the example env file and fill in any values you need to override:

```bash
cp .env.example .env
```

The defaults in `.env.example` work for local development without modification.

## Starting Local Services

```bash
# Start Postgres and Redis in the background
make dev.infra

# Apply database migrations
make db.migrate
```

## Running the Applications

Open two terminal windows:

```bash
# Terminal 1 — API (http://localhost:8000)
make dev.api

# Terminal 2 — Web (http://localhost:3000)
make dev.web
```

### API documentation

When `dev.api` is running, interactive API docs are available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Running Tests

```bash
make test          # all tests
make test.api      # API tests only
make test.watch    # watch mode
```

## Code Quality

```bash
make lint          # ESLint + ruff
make format        # Prettier + ruff format
make type-check    # tsc + pyright
make check         # run everything (mirrors CI)
```

## Database Management

```bash
make db.migrate               # apply pending migrations
make db.rollback              # roll back last migration
make db.revision MSG="..."    # create new migration
make db.reset                 # drop & recreate (destructive)
```

## Resetting the Environment

```bash
make reset         # stop services, wipe volumes, restart, re-migrate
```

## Troubleshooting

**Port conflicts** — if 5432 or 6379 are already in use, stop existing services or update `infra/docker-compose.yml` to use different ports.

**`uv sync` fails** — ensure Python ≥ 3.12 is active: `python --version`.

**Pre-commit hooks fail on first run** — run `pre-commit run --all-files` to see all issues at once.
