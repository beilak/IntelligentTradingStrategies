"""Initial schema.

Revision ID: 202605210001
Revises:
Create Date: 2026-05-21 00:00:00.000000

"""
from typing import Sequence, Union

revision: str = "202605210001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
