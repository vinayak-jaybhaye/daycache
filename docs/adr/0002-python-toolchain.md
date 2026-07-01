# ADR-0002: Python Toolchain

**Date**: 2026-07-01
**Status**: Accepted

## Context

We needed to choose a consistent set of tools for Python dependency management, linting, formatting, and type checking in `apps/api`.

## Decision

| Concern | Tool | Rationale |
|---|---|---|
| Package management | **uv** | Extremely fast, first-class workspace support, lockfile, replaces pip + venv + pip-tools |
| Linting | **ruff** | Rust-based, replaces flake8 + isort + pyupgrade, configurable via pyproject.toml |
| Formatting | **ruff format** | Replaces Black, same config file, no extra dep |
| Type checking | **Pyright** (strict mode) | Fast, excellent VS Code / Pylance integration, catches more errors than mypy in strict mode |
| Testing | **pytest** + **pytest-asyncio** | Industry standard; asyncio_mode = "auto" removes boilerplate |
| Test HTTP client | **httpx** | Required for async FastAPI test client; replaces requests in tests |

## Consequences

**Positive:**
- Single tool (ruff) replaces ~4 tools — simpler configuration.
- `uv` workspaces mean one lockfile for the entire Python codebase.
- Pyright strict mode catches null-safety and missing return type issues at write-time.

**Negative:**
- Pyright strict mode can be noisy during early development. Developers must type annotate everything.
- `uv` is newer than pip — some legacy guides won't apply.

## Alternatives Considered

- **Poetry**: Mature but slow dependency resolution; no workspace support.
- **mypy**: The original Python type checker, but slower and less strict by default than Pyright in strict mode.
- **Black + isort**: Replaced by `ruff format` + `ruff --select I`, fewer tools to manage.
