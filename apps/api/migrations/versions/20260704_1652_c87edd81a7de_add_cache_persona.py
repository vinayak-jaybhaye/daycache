"""add_cache_persona

Revision ID: c87edd81a7de
Revises: d1557a287b52
Create Date: 2026-07-04 16:52:43.839911+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c87edd81a7de"
down_revision: str | None = "d1557a287b52"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ai_persona_name_check", "user_settings", type_="check")
    op.create_check_constraint(
        "ai_persona_name_check",
        "user_settings",
        "ai_persona_name IN ('Mira', 'Sage', 'Echo', 'Jour', 'Nova', 'Cache')",
    )


def downgrade() -> None:
    op.drop_constraint("ai_persona_name_check", "user_settings", type_="check")
    op.create_check_constraint(
        "ai_persona_name_check",
        "user_settings",
        "ai_persona_name IN ('Mira', 'Sage', 'Echo', 'Jour', 'Nova')",
    )
