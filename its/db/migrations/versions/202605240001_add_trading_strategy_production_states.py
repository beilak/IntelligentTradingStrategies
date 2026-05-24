"""Add trading strategy production states.

Revision ID: 202605240001
Revises: 202605230003
Create Date: 2026-05-24 00:01:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "202605240001"
down_revision: Union[str, Sequence[str], None] = "202605230003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "trading_strategy_production_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("strategy_name", sa.String(length=255), nullable=False),
        sa.Column("is_prod_ready", sa.Boolean(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("updated_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "strategy_name", name="uq_trading_strategy_production_states_strategy_name"
        ),
    )
    op.create_index(
        "ix_trading_strategy_production_states_strategy_name",
        "trading_strategy_production_states",
        ["strategy_name"],
        unique=False,
    )
    op.create_index(
        "ix_trading_strategy_production_states_is_prod_ready",
        "trading_strategy_production_states",
        ["is_prod_ready"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_trading_strategy_production_states_is_prod_ready",
        table_name="trading_strategy_production_states",
    )
    op.drop_index(
        "ix_trading_strategy_production_states_strategy_name",
        table_name="trading_strategy_production_states",
    )
    op.drop_table("trading_strategy_production_states")
