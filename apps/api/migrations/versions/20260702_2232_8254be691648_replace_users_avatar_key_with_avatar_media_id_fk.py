"""Replace users.avatar_key with avatar_media_id FK.

Revision ID: 8254be691648
Revises: 52903c9f9328
Create Date: 2026-07-02 22:32:00 UTC
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "8254be691648"
down_revision = "52903c9f9328"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the old plain-text avatar_key column from users.
    op.drop_column("users", "avatar_key")

    # Add avatar_media_id as a nullable UUID FK referencing media.id.
    # ondelete="SET NULL" ensures Postgres auto-clears the reference if the
    # linked media record is deleted, preventing dangling references.
    op.add_column(
        "users",
        sa.Column(
            "avatar_media_id",
            sa.UUID(as_uuid=False),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_users_avatar_media_id_media",
        "users",
        "media",
        ["avatar_media_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_users_avatar_media_id_media", "users", type_="foreignkey")
    op.drop_column("users", "avatar_media_id")

    # Restore the original plain-text column (empty — data was not migrated).
    op.add_column(
        "users",
        sa.Column("avatar_key", sa.Text(), nullable=True),
    )
