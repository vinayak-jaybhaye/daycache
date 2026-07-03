"""rename_device_and_session_fields_and_add_revoked_at

Revision ID: 7c8cae8aead6
Revises: 5dfd628c3a90
Create Date: 2026-07-02 13:51:37.950076+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7c8cae8aead6"
down_revision: str | None = "5dfd628c3a90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Rename columns preserving data
    op.alter_column("devices", "device_identifier", new_column_name="installation_id")
    op.alter_column("sessions", "ip_address", new_column_name="created_ip")
    op.alter_column("sessions", "user_agent", new_column_name="created_user_agent")

    # Drop old constraint and create new one
    op.drop_constraint(
        "devices_user_id_device_identifier_key", "devices", type_="unique"
    )
    op.create_unique_constraint(
        "devices_user_id_installation_id_key", "devices", ["user_id", "installation_id"]
    )

    # Add revoked_at to sessions
    op.add_column(
        "sessions", sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    # Remove revoked_at column
    op.drop_column("sessions", "revoked_at")

    # Drop new constraint and recreate old one
    op.drop_constraint("devices_user_id_installation_id_key", "devices", type_="unique")
    op.create_unique_constraint(
        "devices_user_id_device_identifier_key",
        "devices",
        ["user_id", "device_identifier"],
    )

    # Rename columns back
    op.alter_column("sessions", "created_user_agent", new_column_name="user_agent")
    op.alter_column("sessions", "created_ip", new_column_name="ip_address")
    op.alter_column("devices", "installation_id", new_column_name="device_identifier")
