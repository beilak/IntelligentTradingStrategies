"""Add RSS items.

Revision ID: 202605210002
Revises: 202605210001
Create Date: 2026-05-21 00:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "202605210002"
down_revision: Union[str, Sequence[str], None] = "202605210001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rss_items",
        sa.Column("pub_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("pub_date", "title", "source"),
    )


def downgrade() -> None:
    op.drop_table("rss_items")
