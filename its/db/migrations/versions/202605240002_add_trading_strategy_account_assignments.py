"""Add trading strategy account assignments.

Revision ID: 202605240002
Revises: 202605240001
Create Date: 2026-05-24 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "202605240002"
down_revision: Union[str, Sequence[str], None] = "202605240001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "trading_strategy_account_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", sa.String(length=80), nullable=False),
        sa.Column("strategy_name", sa.String(length=255), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("assigned_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "account_id",
            "strategy_name",
            name="uq_trading_strategy_account_assignments_account_strategy",
        ),
    )
    op.create_index(
        "ix_trading_strategy_account_assignments_account_id",
        "trading_strategy_account_assignments",
        ["account_id"],
        unique=False,
    )
    op.create_index(
        "ix_trading_strategy_account_assignments_strategy_name",
        "trading_strategy_account_assignments",
        ["strategy_name"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_trading_strategy_account_assignments_strategy_name",
        table_name="trading_strategy_account_assignments",
    )
    op.drop_index(
        "ix_trading_strategy_account_assignments_account_id",
        table_name="trading_strategy_account_assignments",
    )
    op.drop_table("trading_strategy_account_assignments")
