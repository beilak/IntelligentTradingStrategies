from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from its.db.models import (
    AuthAuditLog,
    AuthPermission,
    AuthRole,
    AuthRolePermission,
    AuthUser,
    AuthUserRole,
)
from its.tech_system.auth.rbac import (
    BOOTSTRAP_ADMIN_ROLE_CODES,
    DEFAULT_ROLE_CODE,
    PERMISSIONS,
    ROLES,
)


def active_role_clause() -> object:
    now = datetime.now(UTC)
    return or_(AuthUserRole.expires_at.is_(None), AuthUserRole.expires_at > now)


def seed_rbac_catalog(session: Session) -> None:
    existing_permissions = set(session.scalars(select(AuthPermission.code)).all())
    for permission in PERMISSIONS:
        if permission.code in existing_permissions:
            continue
        session.add(
            AuthPermission(
                id=permission.id,
                code=permission.code,
                domain=permission.domain,
                resource=permission.resource,
                action=permission.action,
                title=permission.title,
                description=permission.description or None,
                is_critical=permission.is_critical,
            )
        )

    existing_roles = set(session.scalars(select(AuthRole.code)).all())
    for role in ROLES:
        if role.code in existing_roles:
            continue
        session.add(
            AuthRole(
                id=role.id,
                code=role.code,
                title=role.title,
                description=role.description,
                is_system=role.is_system,
                is_assignable=role.is_assignable,
            )
        )

    session.flush()

    for role in ROLES:
        for permission_code in role.permission_codes:
            permission_id = next(
                permission.id
                for permission in PERMISSIONS
                if permission.code == permission_code
            )
            existing_link = session.get(AuthRolePermission, (role.id, permission_id))
            if existing_link is None:
                session.add(
                    AuthRolePermission(
                        role_id=role.id,
                        permission_id=permission_id,
                    )
                )


def get_role_codes(session: Session, user: AuthUser) -> list[str]:
    return list(
        session.scalars(
            select(AuthRole.code)
            .join(AuthUserRole, AuthUserRole.role_id == AuthRole.id)
            .where(AuthUserRole.user_id == user.id, active_role_clause())
            .order_by(AuthRole.code)
        )
    )


def get_roles(session: Session, user: AuthUser) -> list[AuthRole]:
    return list(
        session.scalars(
            select(AuthRole)
            .join(AuthUserRole, AuthUserRole.role_id == AuthRole.id)
            .where(AuthUserRole.user_id == user.id, active_role_clause())
            .order_by(AuthRole.code)
        )
    )


def get_effective_permission_codes(session: Session, user: AuthUser) -> list[str]:
    return list(
        session.scalars(
            select(AuthPermission.code)
            .join(
                AuthRolePermission,
                AuthRolePermission.permission_id == AuthPermission.id,
            )
            .join(AuthUserRole, AuthUserRole.role_id == AuthRolePermission.role_id)
            .where(AuthUserRole.user_id == user.id, active_role_clause())
            .distinct()
            .order_by(AuthPermission.code)
        )
    )


def user_has_permission(session: Session, user: AuthUser, permission: str) -> bool:
    return permission in set(get_effective_permission_codes(session, user))


def ensure_default_user_roles(
    session: Session,
    user: AuthUser,
    bootstrap_admin_email: str | None = None,
) -> list[str]:
    target_roles = [DEFAULT_ROLE_CODE]
    if bootstrap_admin_email and user.email == bootstrap_admin_email.strip().lower():
        target_roles.extend(BOOTSTRAP_ADMIN_ROLE_CODES)
    return assign_roles_to_user(
        session=session,
        user=user,
        role_codes=target_roles,
        assigned_by=None,
        reason="default role bootstrap",
    )


def assign_roles_to_user(
    *,
    session: Session,
    user: AuthUser,
    role_codes: list[str] | tuple[str, ...],
    assigned_by: AuthUser | None,
    reason: str | None,
) -> list[str]:
    roles = list(session.scalars(select(AuthRole).where(AuthRole.code.in_(role_codes))))
    existing_role_ids = set(
        session.scalars(
            select(AuthUserRole.role_id).where(
                AuthUserRole.user_id == user.id,
                AuthUserRole.role_id.in_([role.id for role in roles]),
            )
        )
    )

    assigned_codes: list[str] = []
    for role in roles:
        if role.id in existing_role_ids:
            continue
        session.add(
            AuthUserRole(
                user_id=user.id,
                role_id=role.id,
                assigned_by=assigned_by.id if assigned_by else None,
                reason=reason,
            )
        )
        assigned_codes.append(role.code)

    if assigned_codes:
        user.role_version += 1
    return assigned_codes


def revoke_role_from_user(
    *,
    session: Session,
    user: AuthUser,
    role_code: str,
) -> bool:
    role = session.scalar(select(AuthRole).where(AuthRole.code == role_code))
    if role is None:
        return False

    assignment = session.get(AuthUserRole, (user.id, role.id))
    if assignment is None:
        return False

    session.delete(assignment)
    user.role_version += 1
    return True


def bump_users_with_role(session: Session, role_id: UUID) -> None:
    users = list(
        session.scalars(
            select(AuthUser)
            .join(AuthUserRole, AuthUserRole.user_id == AuthUser.id)
            .where(AuthUserRole.role_id == role_id)
        )
    )
    for user in users:
        user.role_version += 1


def replace_role_permissions(
    *,
    session: Session,
    role: AuthRole,
    permission_codes: list[str],
) -> None:
    permissions = list(
        session.scalars(
            select(AuthPermission).where(AuthPermission.code.in_(permission_codes))
        )
    )
    found_codes = {permission.code for permission in permissions}
    missing_codes = sorted(set(permission_codes) - found_codes)
    if missing_codes:
        raise ValueError(f"Unknown permissions: {', '.join(missing_codes)}")

    session.execute(
        delete(AuthRolePermission).where(AuthRolePermission.role_id == role.id)
    )
    for permission in permissions:
        session.add(AuthRolePermission(role_id=role.id, permission_id=permission.id))
    bump_users_with_role(session, role.id)


def get_role_permission_codes(session: Session, role: AuthRole) -> list[str]:
    return list(
        session.scalars(
            select(AuthPermission.code)
            .join(
                AuthRolePermission,
                AuthRolePermission.permission_id == AuthPermission.id,
            )
            .where(AuthRolePermission.role_id == role.id)
            .order_by(AuthPermission.code)
        )
    )


def write_audit_event(
    *,
    session: Session,
    actor: AuthUser | None,
    action: str,
    object_type: str,
    object_id: str | None = None,
    before: dict[str, object] | None = None,
    after: dict[str, object] | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    session.add(
        AuthAuditLog(
            actor_user_id=actor.id if actor else None,
            action=action,
            object_type=object_type,
            object_id=object_id,
            before_json=before,
            after_json=after,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    )
