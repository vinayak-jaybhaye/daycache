"""add_ai_persona_name

Revision ID: d1557a287b52
Revises: 28cf671fef75
Create Date: 2026-07-04 16:44:25.256281+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1557a287b52"
down_revision: str | None = "28cf671fef75"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column("ai_persona_name", sa.Text(), server_default="Mira", nullable=False),
    )
    op.create_check_constraint(
        "ai_persona_name_check",
        "user_settings",
        "ai_persona_name IN ('Mira', 'Sage', 'Echo', 'Jour', 'Nova')",
    )


def downgrade() -> None:
    op.drop_constraint("ai_persona_name_check", "user_settings")
    op.drop_column("user_settings", "ai_persona_name")
