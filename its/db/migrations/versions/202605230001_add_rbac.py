"""Add RBAC catalog.

Revision ID: 202605230001
Revises: 202605220001
Create Date: 2026-05-23 00:00:00.000000

"""

from datetime import UTC, datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from its.tech_system.auth.rbac import PERMISSIONS, ROLES, stable_permission_id

revision: str = "202605230001"
down_revision: Union[str, Sequence[str], None] = "202605220001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "auth_roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.Column("is_assignable", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_auth_roles_code"),
    )
    op.create_index("ix_auth_roles_code", "auth_roles", ["code"], unique=False)

    op.create_table(
        "auth_permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=255), nullable=False),
        sa.Column("domain", sa.String(length=64), nullable=False),
        sa.Column("resource", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_critical", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_auth_permissions_code"),
    )
    op.create_index(
        "ix_auth_permissions_code", "auth_permissions", ["code"], unique=False
    )

    op.create_table(
        "auth_role_permissions",
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("permission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["permission_id"], ["auth_permissions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["role_id"], ["auth_roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("role_id", "permission_id"),
    )

    op.create_table(
        "auth_user_roles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assigned_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["assigned_by"], ["auth_users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["role_id"], ["auth_roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["auth_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "role_id"),
    )

    op.create_table(
        "auth_role_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requester_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column("decision_comment", sa.Text(), nullable=True),
        sa.Column("decided_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["decided_by"], ["auth_users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["requested_role_id"], ["auth_roles.id"]),
        sa.ForeignKeyConstraint(
            ["requester_id"], ["auth_users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_auth_role_requests_status", "auth_role_requests", ["status"], unique=False
    )

    op.create_table(
        "auth_audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=255), nullable=False),
        sa.Column("object_type", sa.String(length=128), nullable=False),
        sa.Column("object_id", sa.String(length=255), nullable=True),
        sa.Column(
            "before_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("after_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["auth_users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_auth_audit_log_action", "auth_audit_log", ["action"], unique=False
    )

    seed_rbac_catalog()


def seed_rbac_catalog() -> None:
    now = datetime(2026, 5, 23, tzinfo=UTC)

    permissions_table = sa.table(
        "auth_permissions",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("code", sa.String()),
        sa.column("domain", sa.String()),
        sa.column("resource", sa.String()),
        sa.column("action", sa.String()),
        sa.column("title", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("is_critical", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        permissions_table,
        [
            {
                "id": permission.id,
                "code": permission.code,
                "domain": permission.domain,
                "resource": permission.resource,
                "action": permission.action,
                "title": permission.title,
                "description": permission.description or None,
                "is_critical": permission.is_critical,
                "created_at": now,
                "updated_at": now,
            }
            for permission in PERMISSIONS
        ],
    )

    roles_table = sa.table(
        "auth_roles",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("code", sa.String()),
        sa.column("title", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("is_system", sa.Boolean()),
        sa.column("is_assignable", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        roles_table,
        [
            {
                "id": role.id,
                "code": role.code,
                "title": role.title,
                "description": role.description,
                "is_system": role.is_system,
                "is_assignable": role.is_assignable,
                "created_at": now,
                "updated_at": now,
            }
            for role in ROLES
        ],
    )

    role_permissions_table = sa.table(
        "auth_role_permissions",
        sa.column("role_id", postgresql.UUID(as_uuid=True)),
        sa.column("permission_id", postgresql.UUID(as_uuid=True)),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        role_permissions_table,
        [
            {
                "role_id": role.id,
                "permission_id": stable_permission_id(permission_code),
                "created_at": now,
            }
            for role in ROLES
            for permission_code in role.permission_codes
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_auth_audit_log_action", table_name="auth_audit_log")
    op.drop_table("auth_audit_log")
    op.drop_index("ix_auth_role_requests_status", table_name="auth_role_requests")
    op.drop_table("auth_role_requests")
    op.drop_table("auth_user_roles")
    op.drop_table("auth_role_permissions")
    op.drop_index("ix_auth_permissions_code", table_name="auth_permissions")
    op.drop_table("auth_permissions")
    op.drop_index("ix_auth_roles_code", table_name="auth_roles")
    op.drop_table("auth_roles")
