"""Create memories table with pgvector cosine index.

Revision ID: a1b2c3d4e5f6
Revises: f6bf631ab650
Create Date: 2026-06-24 18:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "f6bf631ab650"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_IVFFLAT_LISTS = 100


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "memories",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_memories_symbol", "memories", ["symbol"])
    op.execute(
        "CREATE INDEX ix_memories_embedding ON memories "
        f"USING ivfflat (embedding vector_cosine_ops) WITH (lists = {_IVFFLAT_LISTS})"
    )


def downgrade() -> None:
    op.drop_index("ix_memories_embedding", table_name="memories")
    op.drop_index("ix_memories_symbol", table_name="memories")
    op.drop_table("memories")
