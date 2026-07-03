"""add embedding_status to journal_entries

Revision ID: 70c94d9cd39c
Revises: 6ed92ae59d18
Create Date: 2026-07-03 17:13:19.641185+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "70c94d9cd39c"
down_revision: str | None = "6ed92ae59d18"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create the custom enum type first
    op.execute(
        "CREATE TYPE embedding_status AS ENUM ('pending', 'processing', 'completed', 'failed')"
    )
    op.add_column(
        "journal_entries",
        sa.Column(
            "embedding_status",
            sa.Enum(
                "pending", "processing", "completed", "failed", name="embedding_status"
            ),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("journal_entries", "embedding_status")
    # Drop the custom enum type
    op.execute("DROP TYPE embedding_status")
