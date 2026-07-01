# Database Design

## Engine

PostgreSQL 16. Async access via SQLAlchemy 2.0 with `asyncpg` driver.

## Migrations

All schema changes must go through **Alembic** migrations. Never modify the database schema manually.

```bash
# Create a new migration (after changing SQLAlchemy models)
make db.revision MSG="add journal entries table"

# Apply migrations
make db.migrate

# Roll back one migration
make db.rollback
```

Migration files live in `apps/api/migrations/versions/`.

## Conventions

### Table naming
- Lowercase snake_case plural nouns: `users`, `journal_entries`, `media_files`
- Junction tables: `{table_a}_{table_b}` (e.g., `entry_tags`)

### Column naming
- `id` — UUID primary key (`gen_random_uuid()`)
- `created_at` — timestamp with timezone, default `now()`
- `updated_at` — timestamp with timezone, updated via trigger
- `deleted_at` — nullable, used for soft deletes

### Primary keys
All tables use UUID v4 primary keys. Avoid sequential integer IDs.

### Soft deletes
Records are soft-deleted by setting `deleted_at`. Queries must filter `WHERE deleted_at IS NULL` by default.

### Indexes
- Always index foreign keys
- Add indexes on columns used in `WHERE`, `ORDER BY`, or `JOIN` clauses
- Use partial indexes where appropriate (e.g., `WHERE deleted_at IS NULL`)

## Core Tables (Planned)

> These are described here for planning purposes. Actual schemas are defined in SQLAlchemy models.

| Table | Description |
|---|---|
| `users` | User accounts |
| `journals` | Named collections of entries |
| `entries` | Individual journal entries (text, rich content) |
| `media_files` | Uploaded images, audio, video |
| `entry_media` | Junction: entries ↔ media files |
| `tags` | User-defined tags |
| `entry_tags` | Junction: entries ↔ tags |

## Connection Pooling

SQLAlchemy async engine uses `asyncpg` with a connection pool. Pool settings are configured in `apps/api/app/db/session.py`.

## Backups

Local development uses Docker volumes. Production backups are handled separately (see [Deployment](deployment.md)).
