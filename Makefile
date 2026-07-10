# DayCache Makefile
# Run `make help` to see all available targets.

.DEFAULT_GOAL := help
.PHONY: help setup dev.web dev.api dev.infra lint format type-check test \
        db.migrate db.rollback db.reset reset check

PNPM        := pnpm
UV          := uv
UV_API      := cd apps/api && $(UV) run
DOCKER      := docker compose -f infra/docker-compose.yml

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

help: ## Show this help message
	@grep -E '^[a-zA-Z_.-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' \
		| sort

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

setup: ## Install all dependencies and git hooks
	$(PNPM) install
	$(UV) sync
	pre-commit install
	@echo "\n✅  Setup complete. Run 'make dev.infra' to start local services."

# ---------------------------------------------------------------------------
# Development servers
# ---------------------------------------------------------------------------

dev.web: ## Start the Next.js dev server
	$(PNPM) --filter @daycache/web dev

dev.api: ## Start the FastAPI dev server (hot-reload)
	$(UV_API) uvicorn app.main:app --reload --port 8000

dev.worker.media:
	$(UV_API) arq app.workers.arq_settings.MediaWorkerSettings

dev.worker.embedding:
	$(UV_API) arq app.workers.arq_settings.EmbeddingWorkerSettings

dev.worker.ai:
	$(UV_API) arq app.workers.arq_settings.AIWorkerSettings

dev.workers: ## Start all three background workers in parallel
	$(MAKE) -j3 dev.worker.media dev.worker.embedding dev.worker.ai

dev.all: ## Start the FastAPI server and all workers in parallel
	$(MAKE) -j4 dev.api dev.worker.media dev.worker.embedding dev.worker.ai

dev.infra: ## Start local infrastructure (Postgres, Redis) in the background
	$(DOCKER) up -d

# ---------------------------------------------------------------------------
# Code quality
# ---------------------------------------------------------------------------

lint: ## Lint Python (ruff) and TypeScript (ESLint)
	$(UV_API) ruff check app/
	$(PNPM) --filter @daycache/web lint

format: ## Auto-format Python (ruff) and TypeScript (Prettier)
	$(UV_API) ruff format app/
	$(UV_API) ruff check --fix app/
	$(PNPM) --filter @daycache/web format

format.check: ## Check formatting without writing changes (CI mode)
	$(UV_API) ruff format --check app/
	$(PNPM) --filter @daycache/web format:check

type-check: ## Run Pyright (Python) and tsc (TypeScript)
	$(UV_API) pyright
	$(PNPM) --filter @daycache/web type-check

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

TEST_DATABASE_URL ?= postgresql+asyncpg://daycache:daycache@localhost:5432/daycache_test

test: ## Run all tests
	$(UV_API) env DATABASE_URL="$(TEST_DATABASE_URL)" pytest

test.api: ## Run API tests only
	$(UV_API) env DATABASE_URL="$(TEST_DATABASE_URL)" pytest tests/ -v

test.watch: ## Run API tests in watch mode
	$(UV_API) env DATABASE_URL="$(TEST_DATABASE_URL)" pytest tests/ -v --tb=short -p no:cacheprovider

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

db.migrate: ## Apply all pending Alembic migrations
	$(UV_API) alembic upgrade head

db.rollback: ## Roll back the last Alembic migration
	$(UV_API) alembic downgrade -1

db.revision: ## Create a new Alembic migration (usage: make db.revision MSG="add users")
	$(UV_API) alembic revision --autogenerate -m "$(MSG)"

db.reset: ## Drop and recreate the database, then run all migrations
	@echo "⚠️  Resetting database..."
	$(DOCKER) exec postgres psql -U daycache -c "DROP DATABASE IF EXISTS daycache;" postgres
	$(DOCKER) exec postgres psql -U daycache -c "CREATE DATABASE daycache;" postgres
	$(MAKE) db.migrate
	@echo "✅  Database reset complete."

db.seed: ## Seed the database with sample data (usage: make db.seed COUNT=1000)
	$(UV_API) python seed_db.py $(COUNT)

# ---------------------------------------------------------------------------
# Infrastructure
# ---------------------------------------------------------------------------

infra.up: ## Start all local infrastructure services
	$(DOCKER) up -d

infra.down: ## Stop all local infrastructure services
	$(DOCKER) down

infra.logs: ## Tail infrastructure logs
	$(DOCKER) logs -f

reset: ## Stop all services, wipe volumes, and restart fresh
	@echo "⚠️  Full environment reset..."
	$(DOCKER) down -v
	$(DOCKER) up -d
	sleep 3
	$(MAKE) db.migrate
	@echo "✅  Environment reset complete."

# ---------------------------------------------------------------------------
# CI equivalent — run everything
# ---------------------------------------------------------------------------

check: lint format.check type-check test ## Run all checks (lint + types + tests) — mirrors CI
