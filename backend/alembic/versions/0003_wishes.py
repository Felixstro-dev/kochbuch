"""wishes board

Revision ID: 0003_wishes
Revises: 0002_recipes
Create Date: 2026-10-31

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_wishes"
down_revision: str | None = "0002_recipes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "wishes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("text", sa.String(length=300), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("done_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_wishes_text", "wishes", ["text"], unique=False)
    op.create_index("ix_wishes_status", "wishes", ["status"], unique=False)
    op.create_index("ix_wishes_created_at", "wishes", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_wishes_created_at", table_name="wishes")
    op.drop_index("ix_wishes_status", table_name="wishes")
    op.drop_index("ix_wishes_text", table_name="wishes")
    op.drop_table("wishes")
