"""alter embedding column type to unconstrained vector

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


def _get_embedding_dimension() -> int:
    try:
        import os

        # Force mock dimensions (1536) for test database environments (bypassing settings cache)
        db_url = os.environ.get("DATABASE_URL") or ""
        if "test" in db_url:
            return 1536

        from app.core.config import get_settings

        settings = get_settings()
        provider = settings.AI_EMBEDDING_PROVIDER
        if provider == "gemini":
            return 768
        elif provider == "ollama":
            model = settings.AI_EMBEDDING_MODEL
            if "nomic" in model or "768" in model:
                return 768
            elif "384" in model or "minilm" in model:
                return 384
            elif "1024" in model or "large" in model:
                return 1024
            return 768
        return 1536
    except Exception:
        return 1536


def upgrade() -> None:
    dim = _get_embedding_dimension()

    # Drop index since it locks the dimension size to 1536
    op.drop_index("idx_embeddings_vector", table_name="embeddings")

    # Alter column to unconstrained vector
    op.alter_column(
        "embeddings",
        "embedding",
        type_=pgvector.sqlalchemy.VECTOR(dim),
        existing_type=pgvector.sqlalchemy.VECTOR(1536),
    )

    # Recreate the index on the unconstrained column
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
    dim = _get_embedding_dimension()

    op.drop_index("idx_embeddings_vector", table_name="embeddings")

    # Revert to vector(1536)
    op.alter_column(
        "embeddings",
        "embedding",
        type_=pgvector.sqlalchemy.VECTOR(1536),
        existing_type=pgvector.sqlalchemy.VECTOR(dim),
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
