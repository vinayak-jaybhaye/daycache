# Coding Guidelines

Standards for writing consistent, maintainable code in DayCache.

## General Principles

1. **Clarity over cleverness** — write code for the next developer, not the compiler.
2. **Prefer established patterns** — when adding new code, look for existing patterns in the codebase first.
3. **No magic** — avoid hidden side effects, implicit behavior, or surprising abstractions.
4. **Fail loudly** — raise errors explicitly; never silently swallow exceptions.
5. **One responsibility** — functions and classes should do one thing well.

---

## Python (Backend)

### Style
- Formatted and linted by **ruff** (enforced automatically via pre-commit).
- Line length: **88** characters.
- Imports: **isort** order enforced by ruff's `I` ruleset (stdlib → third-party → local).
- Type annotations are **required** on all public functions and class attributes.
- Pyright runs in `strict` mode — no `Any` unless justified with a comment.

### Naming
| Entity | Convention | Example |
|---|---|---|
| Module | `snake_case` | `journal_service.py` |
| Class | `PascalCase` | `JournalService` |
| Function / variable | `snake_case` | `get_entry_by_id` |
| Constant | `UPPER_SNAKE_CASE` | `MAX_PAGE_SIZE = 100` |
| Private | leading `_` | `_build_query` |

### Module structure (per feature)
Each `modules/{feature}/` directory follows this layout:
```
router.py      # FastAPI router — only HTTP concerns
service.py     # Business logic — calls repositories
repository.py  # Database queries — SQLAlchemy only
schemas.py     # Pydantic request/response models
models.py      # SQLAlchemy ORM models (when added)
```

### Error handling
- Use FastAPI's `HTTPException` at the router layer only.
- Services raise domain exceptions (e.g., `JournalNotFoundError`).
- Routers catch domain exceptions and convert them to HTTP responses.

### Tests
- One test file per module file: `test_journal_service.py` → `journal_service.py`.
- Use `pytest-asyncio` for async tests.
- Use `httpx.AsyncClient` for integration tests against the FastAPI app.
- Factory functions or fixtures for test data — no raw SQL in tests.

---

## TypeScript (Frontend)

### Style
- Formatted by **Prettier** and linted by **ESLint** (enforced via pre-commit).
- Line length: **100** characters.
- No `any` — use `unknown` and narrow where needed.
- Prefer `interface` over `type` for object shapes; use `type` for unions and primitives.

### Naming
| Entity | Convention | Example |
|---|---|---|
| Component | `PascalCase` | `JournalEntry.tsx` |
| Hook | `camelCase` prefixed `use` | `useJournalEntry.ts` |
| Utility | `camelCase` | `formatDate.ts` |
| Type/Interface | `PascalCase` | `JournalEntry`, `ApiResponse` |
| CSS class | Tailwind utilities only | — |

### Component conventions
- Prefer **named exports** over default exports for non-page components.
- Keep components small — if a component exceeds ~150 lines, split it.
- Co-locate component-specific types at the top of the file.
- Extract complex logic to a custom hook.

### Feature module structure
```
features/{feature}/
  components/   Feature-specific components
  hooks/        Feature-specific hooks
  api.ts        API calls for this feature
  types.ts      Feature-specific types
  index.ts      Public API (barrel export)
```

### State management
- Server state: fetch via `lib/api/` — React Server Components where possible.
- Client state: React `useState` / `useReducer` for local UI state.
- Global state: Context API for lightweight shared state (auth, theme).
- Avoid over-engineering — no Redux unless clearly justified.

---

## Git

- **Commits** follow [Conventional Commits](https://www.conventionalcommits.org/):
  - `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`, `ci:`
- **Branches**: `feat/`, `fix/`, `chore/` prefixes (e.g., `feat/journal-crud`).
- **PRs**: squash-merge into `main` after review.
- **No force-push** to `main` or `develop`.

---

## Environment Variables

- Never hardcode environment-specific values.
- All env vars must have an entry in `.env.example` with a comment.
- Access backend config through `app.core.config` (a typed Pydantic `Settings` object).
- Access frontend config through `NEXT_PUBLIC_*` variables only for client-side values.
