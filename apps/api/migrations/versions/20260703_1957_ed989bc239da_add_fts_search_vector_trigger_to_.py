"""add fts search vector trigger to journal_entries

Revision ID: ed989bc239da
Revises: 0411c9ce868b
Create Date: 2026-07-03 19:57:14.267906+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ed989bc239da"
down_revision: str | None = "0411c9ce868b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create trigger function and trigger
    op.execute(
        """
        CREATE OR REPLACE FUNCTION journal_entries_search_vector_update() RETURNS trigger AS $$
        begin
          new.search_vector := to_tsvector('english', coalesce(new.title, '') || ' ' || coalesce(new.content_text, ''));
          return new;
        end
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER tsvectorupdate BEFORE INSERT OR UPDATE
        ON journal_entries FOR EACH ROW EXECUTE FUNCTION
        journal_entries_search_vector_update();
        """
    )
    # 2. Backfill existing journal entries
    op.execute(
        """
        UPDATE journal_entries SET search_vector = to_tsvector('english', coalesce(title, '') || ' ' || coalesce(content_text, ''));
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS tsvectorupdate ON journal_entries;")
    op.execute("DROP FUNCTION IF EXISTS journal_entries_search_vector_update();")
