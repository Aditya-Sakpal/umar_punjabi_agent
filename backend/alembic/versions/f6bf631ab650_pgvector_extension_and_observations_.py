"""pgvector extension and observations embedding

Revision ID: f6bf631ab650
Revises: afb3ca01d67e
Create Date: 2026-06-24 15:55:57.035737

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = 'f6bf631ab650'
down_revision: Union[str, Sequence[str], None] = 'afb3ca01d67e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ivfflat tuning: L2 (`<->`) opclass to match MemoryTool.recall's `ORDER BY embedding <-> :q`.
# lists=100 is pgvector's standard small-dataset default; fine for a demo, retune later if needed.
_IVFFLAT_LISTS = 100


def upgrade() -> None:
    """Create the vector extension, add the embedding column, and build the ivfflat index."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column("observations", sa.Column("embedding", Vector(384), nullable=False))
    op.execute(
        "CREATE INDEX ix_observations_embedding ON observations "
        f"USING ivfflat (embedding vector_l2_ops) WITH (lists = {_IVFFLAT_LISTS})"
    )


def downgrade() -> None:
    """Drop the index and embedding column (leave the extension installed)."""
    op.drop_index("ix_observations_embedding", table_name="observations")
    op.drop_column("observations", "embedding")
