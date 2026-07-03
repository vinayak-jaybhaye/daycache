"""alter embedding column type to 768-dimensional vector

Revision ID: 0411c9ce868b
Revises: 70c94d9cd39c
Create Date: 2026-07-03 18:07:32.640929+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import pgvector
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0411c9ce868b"
down_revision: str | None = "70c94d9cd39c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop index since it locks the dimension size to 1536
    # Drop the IVFFlat index before changing the vector dimension.
    # Vector indexes are tied to the embedding dimension and must be recreated.
    op.drop_index("idx_embeddings_vector", table_name="embeddings")

    # Alter column to 768-dimensional vector
    op.alter_column(
        "embeddings",
        "embedding",
        type_=pgvector.sqlalchemy.VECTOR(768),
        existing_type=pgvector.sqlalchemy.VECTOR(1536),
    )

    # Recreate the index on the 768-dimensional column
    op.create_index(
        "idx_embeddings_vector",
        "embeddings",
        ["embedding"],
        unique=False,
        postgresql_using="ivfflat",
        postgresql_ops={"embedding": "vector_cosine_ops"},
        postgresql_with={"lists": 100},
    )


def downgrade() -> None:
    op.drop_index("idx_embeddings_vector", table_name="embeddings")

    # Revert to vector(1536)
    op.alter_column(
        "embeddings",
        "embedding",
        type_=pgvector.sqlalchemy.VECTOR(1536),
        existing_type=pgvector.sqlalchemy.VECTOR(768),
    )

    # Recreate the 1536-dimensional index
    op.create_index(
        "idx_embeddings_vector",
        "embeddings",
        ["embedding"],
        unique=False,
        postgresql_using="ivfflat",
        postgresql_ops={"embedding": "vector_cosine_ops"},
        postgresql_with={"lists": 100},
    )
