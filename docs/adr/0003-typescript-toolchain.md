# ADR-0003: TypeScript Toolchain

**Date**: 2026-07-01
**Status**: Accepted

## Context

We needed to choose tools for JavaScript/TypeScript dependency management, linting, formatting, and type checking in `apps/web`.

## Decision

| Concern | Tool | Rationale |
|---|---|---|
| Package management | **pnpm** (workspaces) | Fast, disk-efficient, first-class monorepo support, strict dependency isolation |
| Framework | **Next.js 16** (App Router) | Industry standard for React SSR/SSG; built-in TypeScript support |
| Styling | **Tailwind CSS v4** | Utility-first, excellent DX, pairs well with Next.js |
| Linting | **ESLint** (`eslint-config-next`) | Maintained by Vercel, includes React, accessibility, and Next.js-specific rules |
| Formatting | **Prettier** + `prettier-plugin-tailwindcss` | Standard formatter for the React ecosystem; Tailwind plugin auto-sorts classes |
| Type checking | **tsc** (`strict` mode) | TypeScript's own compiler; `noEmit` mode used — Next.js handles transpilation |

## Consequences

**Positive:**
- `eslint-config-next` gives us sensible defaults without manual rule configuration.
- Prettier + tailwindcss plugin eliminates debates about class order.
- `tsc --noEmit` catches type errors independently of the build, enabling fast CI type-check jobs.

**Negative:**
- ESLint + Prettier requires both tools to be configured and coordinated.
- Prettier does not lint — it only formats. ESLint handles correctness, Prettier handles style.

## Alternatives Considered

- **Biome**: A faster Rust-based alternative to ESLint + Prettier combined. Rejected because it lacks a mature Tailwind CSS plugin and `eslint-config-next` compatibility.
- **Yarn / npm**: Rejected in favor of pnpm for performance and workspace strictness.
- **Webpack / Vite**: Replaced by Next.js's built-in Turbopack; no custom bundler configuration needed.
