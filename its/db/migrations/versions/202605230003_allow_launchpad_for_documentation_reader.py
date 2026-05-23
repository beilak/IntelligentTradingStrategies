"""Allow Launchpad for documentation reader.

Revision ID: 202605230003
Revises: 202605230002
Create Date: 2026-05-23 03:00:00.000000

"""

from datetime import UTC, datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "202605230003"
down_revision: Union[str, Sequence[str], None] = "202605230002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("""
            INSERT INTO auth_role_permissions (role_id, permission_id, created_at)
            SELECT r.id, p.id, :created_at
            FROM auth_roles r
            JOIN auth_permissions p ON p.code = 'app.launchpad.read'
            WHERE r.code = 'documentation_reader'
            ON CONFLICT (role_id, permission_id) DO NOTHING
            """).bindparams(created_at=datetime(2026, 5, 23, 3, 0, tzinfo=UTC)))


def downgrade() -> None:
    op.execute(sa.text("""
            DELETE FROM auth_role_permissions rp
            USING auth_roles r, auth_permissions p
            WHERE rp.role_id = r.id
              AND rp.permission_id = p.id
              AND r.code = 'documentation_reader'
              AND p.code = 'app.launchpad.read'
            """))
