"""seed_predefined_moods

Revision ID: 6ed92ae59d18
Revises: 8dd287ab96e6
Create Date: 2026-07-03 11:39:49.151636+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6ed92ae59d18"
down_revision: str | None = "8dd287ab96e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Fixed UUIDs keep the migration idempotent across environments.
MOODS = [
    {
        "id": "11111111-0000-4000-a000-000000000001",
        "name": "happy",
        "color": "#4CAF50",
    },
    {
        "id": "11111111-0000-4000-a000-000000000002",
        "name": "excited",
        "color": "#FBC02D",
    },
    {
        "id": "11111111-0000-4000-a000-000000000003",
        "name": "grateful",
        "color": "#26A69A",
    },
    {
        "id": "11111111-0000-4000-a000-000000000004",
        "name": "hopeful",
        "color": "#42A5F5",
    },
    {
        "id": "11111111-0000-4000-a000-000000000005",
        "name": "calm",
        "color": "#29B6F6",
    },
    {
        "id": "11111111-0000-4000-a000-000000000006",
        "name": "content",
        "color": "#66BB6A",
    },
    {
        "id": "11111111-0000-4000-a000-000000000007",
        "name": "thoughtful",
        "color": "#5C6BC0",
    },
    {
        "id": "11111111-0000-4000-a000-000000000008",
        "name": "neutral",
        "color": "#90A4AE",
    },
    {
        "id": "11111111-0000-4000-a000-000000000009",
        "name": "confused",
        "color": "#78909C",
    },
    {
        "id": "11111111-0000-4000-a000-00000000000a",
        "name": "tired",
        "color": "#9575CD",
    },
    {
        "id": "11111111-0000-4000-a000-00000000000b",
        "name": "stressed",
        "color": "#FF7043",
    },
    {
        "id": "11111111-0000-4000-a000-00000000000c",
        "name": "anxious",
        "color": "#FFA726",
    },
    {
        "id": "11111111-0000-4000-a000-00000000000d",
        "name": "disappointed",
        "color": "#8D6E63",
    },
    {
        "id": "11111111-0000-4000-a000-00000000000e",
        "name": "sad",
        "color": "#42A5F5",
    },
    {
        "id": "11111111-0000-4000-a000-00000000000f",
        "name": "angry",
        "color": "#EF5350",
    },
    {
        "id": "11111111-0000-4000-a000-000000000010",
        "name": "overwhelmed",
        "color": "#AB47BC",
    },
]


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            INSERT INTO moods (id, name, color)
            VALUES (:id, :name, :color)
            ON CONFLICT (id) DO NOTHING
            """
        ),
        MOODS,
    )


def downgrade() -> None:
    conn = op.get_bind()
    ids = [m["id"] for m in MOODS]
    for mood_id in ids:
        conn.execute(
            sa.text("DELETE FROM moods WHERE id = :id"),
            {"id": mood_id},
        )
