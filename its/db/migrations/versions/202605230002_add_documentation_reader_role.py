"""Add minimal documentation reader role.

Revision ID: 202605230002
Revises: 202605230001
Create Date: 2026-05-23 02:00:00.000000

"""

from datetime import UTC, datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from its.tech_system.auth.rbac import ROLES_BY_CODE

revision: str = "202605230002"
down_revision: Union[str, Sequence[str], None] = "202605230001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    now = datetime(2026, 5, 23, 2, 0, tzinfo=UTC)
    role = ROLES_BY_CODE["documentation_reader"]

    op.execute(
        sa.text("""
            INSERT INTO auth_roles (
                id, code, title, description, is_system, is_assignable,
                created_at, updated_at
            )
            VALUES (
                CAST(:id AS UUID), :code, :title, :description, :is_system, :is_assignable,
                :created_at, :updated_at
            )
            ON CONFLICT (code) DO NOTHING
            """).bindparams(
            id=str(role.id),
            code=role.code,
            title=role.title,
            description=role.description,
            is_system=role.is_system,
            is_assignable=role.is_assignable,
            created_at=now,
            updated_at=now,
        )
    )

    for permission_code in role.permission_codes:
        op.execute(
            sa.text("""
                INSERT INTO auth_role_permissions (role_id, permission_id, created_at)
                SELECT r.id, p.id, :created_at
                FROM auth_roles r
                JOIN auth_permissions p ON p.code = :permission_code
                WHERE r.code = :role_code
                ON CONFLICT (role_id, permission_id) DO NOTHING
                """).bindparams(
                role_code=role.code,
                permission_code=permission_code,
                created_at=now,
            )
        )


def downgrade() -> None:
    op.execute(sa.text("""
            DELETE FROM auth_roles
            WHERE code = 'documentation_reader'
            """))
