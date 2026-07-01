# ADR-0001: Monorepo Structure

**Date**: 2026-07-01
**Status**: Accepted

## Context

DayCache requires a Next.js frontend, a FastAPI backend, and eventually a React Native mobile app. All three apps share types, configuration patterns, and developer tooling. We needed to decide whether to use separate repositories or a monorepo.

## Decision

Use a **monorepo** managed by:
- **pnpm workspaces** for JavaScript/TypeScript packages
- **uv workspaces** for Python packages

A single repository root contains `apps/web`, `apps/api`, and `apps/mobile`, with shared `infra/`, `docs/`, and root-level tooling configs.

## Consequences

**Positive:**
- Atomic commits that span frontend and backend changes
- Single place for shared documentation, CI, and conventions
- Easier to keep API contracts and types in sync
- Simpler onboarding — one `make setup` command

**Negative:**
- CI must use path filters to avoid running all jobs on every commit
- A single breaking commit can block all apps (mitigated by CI)
- Slightly more complex initial setup

## Alternatives Considered

- **Separate repos**: Simpler per-app CI, but cross-cutting changes require multiple PRs and coordinated releases.
- **Nx / Turborepo**: More powerful monorepo tooling, but adds significant complexity. Can be adopted later if build performance becomes an issue.
