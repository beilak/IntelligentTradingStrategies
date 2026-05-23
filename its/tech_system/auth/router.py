from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from its.db.models import (
    AuthAuditLog,
    AuthPermission,
    AuthRole,
    AuthRolePermission,
    AuthRoleRequest,
    AuthUser,
    AuthUserRole,
)
from its.db.session import get_session
from its.tech_system.auth.rbac_service import (
    assign_roles_to_user,
    ensure_default_user_roles,
    get_effective_permission_codes,
    get_role_permission_codes,
    get_roles,
    replace_role_permissions,
    revoke_role_from_user,
    user_has_permission,
    write_audit_event,
)
from its.tech_system.auth.schemas import (
    AssignRoleRequest,
    AuditEventResponse,
    AuthResponse,
    LoginRequest,
    LogoutResponse,
    PermissionResponse,
    RefreshTokenRequest,
    RegisterRequest,
    RoleAssignmentResponse,
    RoleCreateRequest,
    RoleRequestCreateRequest,
    RoleRequestDecisionRequest,
    RoleRequestResponse,
    RoleResponse,
    RoleSummary,
    RoleUpdateRequest,
    UpdateUserRequest,
    UserResponse,
)
from its.tech_system.auth.security import (
    AuthTokenError,
    create_jwt_token,
    decode_jwt_token,
    hash_password,
    password_needs_rehash,
    verify_password,
)
from its.tech_system.auth.settings import get_auth_settings

router = APIRouter()
bearer_scheme = HTTPBearer(auto_error=False)

ROLE_REQUEST_PENDING = "pending"
ROLE_REQUEST_APPROVED = "approved"
ROLE_REQUEST_REJECTED = "rejected"
ROLE_REQUEST_CANCELLED = "cancelled"


def auth_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "error": "unauthorized",
            "message": "Authentication token is missing or invalid.",
        },
        headers={"WWW-Authenticate": "Bearer"},
    )


def forbidden_exception(required_permissions: list[str]) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "error": "forbidden",
            "message": "You do not have permission to perform this action.",
            "required_permissions": required_permissions,
        },
    )


def get_request_ip(request: Request) -> str | None:
    if request.client is None:
        return None
    return request.client.host


def get_user_by_email(session: Session, email: str) -> AuthUser | None:
    return session.scalar(select(AuthUser).where(AuthUser.email == email))


def role_summary(role: AuthRole) -> RoleSummary:
    return RoleSummary(code=role.code, title=role.title, description=role.description)


def permission_response(permission: AuthPermission) -> PermissionResponse:
    return PermissionResponse.model_validate(permission)


def build_user_response(session: Session, user: AuthUser) -> UserResponse:
    roles = [role_summary(role) for role in get_roles(session, user)]
    permissions = get_effective_permission_codes(session, user)
    return UserResponse(
        id=user.id,
        email=user.email,
        is_active=user.is_active,
        is_verified=user.is_verified,
        role_version=user.role_version,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        roles=roles,
        permissions=permissions,
    )


def build_role_response(session: Session, role: AuthRole) -> RoleResponse:
    return RoleResponse(
        code=role.code,
        title=role.title,
        description=role.description,
        is_system=role.is_system,
        is_assignable=role.is_assignable,
        permissions=get_role_permission_codes(session, role),
    )


def build_auth_response(session: Session, user: AuthUser) -> AuthResponse:
    roles = [role.code for role in get_roles(session, user)]
    permissions = get_effective_permission_codes(session, user)
    access_token, expires_in = create_jwt_token(
        subject=user.id,
        email=user.email,
        role_version=user.role_version,
        token_type="access",
        roles=roles,
        permissions=permissions,
        env_scopes=["research", "paper"],
    )
    refresh_token, _ = create_jwt_token(
        subject=user.id,
        email=user.email,
        role_version=user.role_version,
        token_type="refresh",
    )
    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        user=build_user_response(session, user),
    )


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[Session, Depends(get_session)],
) -> AuthUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise auth_exception()

    try:
        payload = decode_jwt_token(credentials.credentials, expected_type="access")
        user_id = UUID(str(payload["sub"]))
    except (AuthTokenError, KeyError, ValueError):
        raise auth_exception() from None

    user = session.get(AuthUser, user_id)
    if user is None or not user.is_active:
        raise auth_exception()
    return user


def require_permission(permission: str):
    def dependency(
        current_user: Annotated[AuthUser, Depends(get_current_user)],
        session: Annotated[Session, Depends(get_session)],
    ) -> AuthUser:
        if not user_has_permission(session, current_user, permission):
            raise forbidden_exception([permission])
        return current_user

    return dependency


def get_role_or_404(session: Session, role_code: str) -> AuthRole:
    role = session.scalar(select(AuthRole).where(AuthRole.code == role_code))
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Role not found"
        )
    return role


def get_user_or_404(session: Session, user_id: UUID) -> AuthUser:
    user = session.get(AuthUser, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return user


def get_permissions_or_400(
    session: Session, permission_codes: list[str]
) -> list[AuthPermission]:
    permissions = list(
        session.scalars(
            select(AuthPermission).where(AuthPermission.code.in_(permission_codes))
        )
    )
    found_codes = {permission.code for permission in permissions}
    missing_codes = sorted(set(permission_codes) - found_codes)
    if missing_codes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown permissions: {', '.join(missing_codes)}",
        )
    return permissions


def build_role_request_response(
    session: Session,
    role_request: AuthRoleRequest,
) -> RoleRequestResponse:
    role = session.get(AuthRole, role_request.requested_role_id)
    requester = session.get(AuthUser, role_request.requester_id)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Role not found"
        )
    return RoleRequestResponse(
        id=role_request.id,
        requester_id=role_request.requester_id,
        requester_email=requester.email if requester else None,
        role=role_summary(role),
        status=role_request.status,
        justification=role_request.justification,
        decision_comment=role_request.decision_comment,
        decided_by=role_request.decided_by,
        decided_at=role_request.decided_at,
        created_at=role_request.created_at,
        updated_at=role_request.updated_at,
    )


def audit_metadata(request: Request) -> dict[str, str | None]:
    return {
        "ip_address": get_request_ip(request),
        "user_agent": request.headers.get("user-agent"),
    }


@router.post(
    "/auth/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED
)
def register(
    payload: RegisterRequest,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> AuthResponse:
    if get_user_by_email(session, payload.email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="User already exists"
        )

    user = AuthUser(email=payload.email, password_hash=hash_password(payload.password))
    session.add(user)
    try:
        session.flush()
        ensure_default_user_roles(
            session,
            user,
            bootstrap_admin_email=get_auth_settings().bootstrap_admin_email,
        )
        write_audit_event(
            session=session,
            actor=user,
            action="auth.user.registered",
            object_type="auth_user",
            object_id=str(user.id),
            after={"email": user.email},
            **audit_metadata(request),
        )
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="User already exists"
        ) from None
    session.refresh(user)
    return build_auth_response(session, user)


@router.post("/auth/login", response_model=AuthResponse)
def login(
    payload: LoginRequest,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> AuthResponse:
    user = get_user_by_email(session, payload.email)
    if user is None or not verify_password(payload.password, user.password_hash):
        write_audit_event(
            session=session,
            actor=user,
            action="auth.login.failed",
            object_type="auth_user",
            object_id=str(user.id) if user else payload.email,
            after={"email": payload.email},
            **audit_metadata(request),
        )
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="User is disabled"
        )

    ensure_default_user_roles(
        session,
        user,
        bootstrap_admin_email=get_auth_settings().bootstrap_admin_email,
    )
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)
    user.last_login_at = datetime.now(UTC)
    write_audit_event(
        session=session,
        actor=user,
        action="auth.login.succeeded",
        object_type="auth_user",
        object_id=str(user.id),
        **audit_metadata(request),
    )
    session.commit()
    session.refresh(user)
    return build_auth_response(session, user)


@router.post("/auth/refresh", response_model=AuthResponse)
def refresh(
    payload: RefreshTokenRequest,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> AuthResponse:
    try:
        token_payload = decode_jwt_token(payload.refresh_token, expected_type="refresh")
        user_id = UUID(str(token_payload["sub"]))
    except (AuthTokenError, KeyError, ValueError):
        raise auth_exception() from None

    user = session.get(AuthUser, user_id)
    if user is None or not user.is_active:
        raise auth_exception()

    ensure_default_user_roles(
        session,
        user,
        bootstrap_admin_email=get_auth_settings().bootstrap_admin_email,
    )
    write_audit_event(
        session=session,
        actor=user,
        action="auth.refresh",
        object_type="auth_user",
        object_id=str(user.id),
        **audit_metadata(request),
    )
    session.commit()
    session.refresh(user)
    return build_auth_response(session, user)


@router.get("/auth/me", response_model=UserResponse)
def me(
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> UserResponse:
    return build_user_response(session, current_user)


@router.post("/auth/logout", response_model=LogoutResponse)
def logout(
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> LogoutResponse:
    write_audit_event(
        session=session,
        actor=current_user,
        action="auth.logout",
        object_type="auth_user",
        object_id=str(current_user.id),
        **audit_metadata(request),
    )
    session.commit()
    return LogoutResponse(status="ok")


@router.get("/profile/me", response_model=UserResponse)
def profile_me(
    current_user: Annotated[AuthUser, Depends(require_permission("profile.self.read"))],
    session: Annotated[Session, Depends(get_session)],
) -> UserResponse:
    return build_user_response(session, current_user)


@router.get("/profile/me/roles", response_model=list[RoleAssignmentResponse])
def profile_roles(
    current_user: Annotated[AuthUser, Depends(require_permission("profile.self.read"))],
    session: Annotated[Session, Depends(get_session)],
) -> list[RoleAssignmentResponse]:
    rows = session.execute(
        select(AuthUserRole, AuthRole)
        .join(AuthRole, AuthRole.id == AuthUserRole.role_id)
        .where(AuthUserRole.user_id == current_user.id)
        .order_by(AuthRole.code)
    ).all()
    return [
        RoleAssignmentResponse(
            role=role_summary(role),
            assigned_at=assignment.assigned_at,
            assigned_by=assignment.assigned_by,
            expires_at=assignment.expires_at,
            reason=assignment.reason,
        )
        for assignment, role in rows
    ]


@router.get("/profile/me/permissions", response_model=list[str])
def profile_permissions(
    current_user: Annotated[AuthUser, Depends(require_permission("profile.self.read"))],
    session: Annotated[Session, Depends(get_session)],
) -> list[str]:
    return get_effective_permission_codes(session, current_user)


@router.get("/profile/me/role-requests", response_model=list[RoleRequestResponse])
def my_role_requests(
    current_user: Annotated[
        AuthUser, Depends(require_permission("role.request.create"))
    ],
    session: Annotated[Session, Depends(get_session)],
) -> list[RoleRequestResponse]:
    requests = list(
        session.scalars(
            select(AuthRoleRequest)
            .where(AuthRoleRequest.requester_id == current_user.id)
            .order_by(AuthRoleRequest.created_at.desc())
        )
    )
    return [
        build_role_request_response(session, role_request) for role_request in requests
    ]


@router.post(
    "/profile/me/role-requests",
    response_model=RoleRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_role_request(
    payload: RoleRequestCreateRequest,
    current_user: Annotated[
        AuthUser, Depends(require_permission("role.request.create"))
    ],
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> RoleRequestResponse:
    role = get_role_or_404(session, payload.role_code)
    if not role.is_assignable:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Role is not requestable"
        )

    existing_pending = session.scalar(
        select(AuthRoleRequest).where(
            AuthRoleRequest.requester_id == current_user.id,
            AuthRoleRequest.requested_role_id == role.id,
            AuthRoleRequest.status == ROLE_REQUEST_PENDING,
        )
    )
    if existing_pending is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Pending request for this role already exists",
        )

    role_request = AuthRoleRequest(
        requester_id=current_user.id,
        requested_role_id=role.id,
        status=ROLE_REQUEST_PENDING,
        justification=payload.justification,
    )
    session.add(role_request)
    session.flush()
    write_audit_event(
        session=session,
        actor=current_user,
        action="role.request.created",
        object_type="auth_role_request",
        object_id=str(role_request.id),
        after={"role": role.code},
        **audit_metadata(request),
    )
    session.commit()
    session.refresh(role_request)
    return build_role_request_response(session, role_request)


@router.post(
    "/profile/me/role-requests/{request_id}/cancel", response_model=RoleRequestResponse
)
def cancel_role_request(
    request_id: UUID,
    current_user: Annotated[
        AuthUser, Depends(require_permission("role.request.create"))
    ],
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> RoleRequestResponse:
    role_request = session.get(AuthRoleRequest, request_id)
    if role_request is None or role_request.requester_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Role request not found"
        )
    if role_request.status != ROLE_REQUEST_PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending requests can be cancelled",
        )

    role_request.status = ROLE_REQUEST_CANCELLED
    role_request.updated_at = datetime.now(UTC)
    write_audit_event(
        session=session,
        actor=current_user,
        action="role.request.cancelled",
        object_type="auth_role_request",
        object_id=str(role_request.id),
        **audit_metadata(request),
    )
    session.commit()
    session.refresh(role_request)
    return build_role_request_response(session, role_request)


@router.get("/roles/requestable", response_model=list[RoleResponse])
def requestable_roles(
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> list[RoleResponse]:
    current_role_codes = {role.code for role in get_roles(session, current_user)}
    roles = list(
        session.scalars(
            select(AuthRole)
            .where(AuthRole.is_assignable.is_(True))
            .order_by(AuthRole.code)
        )
    )
    return [
        build_role_response(session, role)
        for role in roles
        if role.code not in current_role_codes
    ]


@router.get("/roles", response_model=list[RoleResponse])
def list_roles(
    _: Annotated[AuthUser, Depends(require_permission("role.read"))],
    session: Annotated[Session, Depends(get_session)],
) -> list[RoleResponse]:
    roles = list(session.scalars(select(AuthRole).order_by(AuthRole.code)))
    return [build_role_response(session, role) for role in roles]


@router.get("/roles/{role_code}", response_model=RoleResponse)
def role_details(
    role_code: str,
    _: Annotated[AuthUser, Depends(require_permission("role.read"))],
    session: Annotated[Session, Depends(get_session)],
) -> RoleResponse:
    return build_role_response(session, get_role_or_404(session, role_code))


@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
def create_role(
    payload: RoleCreateRequest,
    current_user: Annotated[AuthUser, Depends(require_permission("role.create"))],
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> RoleResponse:
    if (
        session.scalar(select(AuthRole).where(AuthRole.code == payload.code))
        is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Role already exists"
        )

    role = AuthRole(
        code=payload.code,
        title=payload.title,
        description=payload.description,
        is_system=False,
        is_assignable=payload.is_assignable,
    )
    session.add(role)
    session.flush()
    if payload.permission_codes:
        permissions = get_permissions_or_400(session, payload.permission_codes)
        for permission in permissions:
            session.add(
                AuthRolePermission(role_id=role.id, permission_id=permission.id)
            )
    write_audit_event(
        session=session,
        actor=current_user,
        action="role.created",
        object_type="auth_role",
        object_id=str(role.id),
        after={"code": role.code},
        **audit_metadata(request),
    )
    session.commit()
    session.refresh(role)
    return build_role_response(session, role)


@router.patch("/roles/{role_code}", response_model=RoleResponse)
def update_role(
    role_code: str,
    payload: RoleUpdateRequest,
    current_user: Annotated[AuthUser, Depends(require_permission("role.update"))],
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> RoleResponse:
    role = get_role_or_404(session, role_code)
    before = {
        "title": role.title,
        "description": role.description,
        "is_assignable": role.is_assignable,
        "permissions": get_role_permission_codes(session, role),
    }
    if payload.title is not None:
        role.title = payload.title
    if payload.description is not None:
        role.description = payload.description
    if payload.is_assignable is not None:
        role.is_assignable = payload.is_assignable
    if payload.permission_codes is not None:
        try:
            replace_role_permissions(
                session=session,
                role=role,
                permission_codes=payload.permission_codes,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
    role.updated_at = datetime.now(UTC)
    write_audit_event(
        session=session,
        actor=current_user,
        action="role.updated",
        object_type="auth_role",
        object_id=str(role.id),
        before=before,
        after={
            "title": role.title,
            "description": role.description,
            "is_assignable": role.is_assignable,
            "permissions": get_role_permission_codes(session, role),
        },
        **audit_metadata(request),
    )
    session.commit()
    session.refresh(role)
    return build_role_response(session, role)


@router.delete("/roles/{role_code}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(
    role_code: str,
    current_user: Annotated[AuthUser, Depends(require_permission("role.delete"))],
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> None:
    role = get_role_or_404(session, role_code)
    if role.is_system:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="System role cannot be deleted",
        )
    write_audit_event(
        session=session,
        actor=current_user,
        action="role.deleted",
        object_type="auth_role",
        object_id=str(role.id),
        before={"code": role.code},
        **audit_metadata(request),
    )
    session.delete(role)
    session.commit()


@router.get("/permissions", response_model=list[PermissionResponse])
def list_permissions(
    _: Annotated[AuthUser, Depends(require_permission("permission.read"))],
    session: Annotated[Session, Depends(get_session)],
) -> list[PermissionResponse]:
    permissions = list(
        session.scalars(select(AuthPermission).order_by(AuthPermission.code))
    )
    return [permission_response(permission) for permission in permissions]


@router.get("/permissions/grouped", response_model=dict[str, list[PermissionResponse]])
def grouped_permissions(
    _: Annotated[AuthUser, Depends(require_permission("permission.read"))],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, list[PermissionResponse]]:
    permissions = list(
        session.scalars(select(AuthPermission).order_by(AuthPermission.code))
    )
    grouped: dict[str, list[PermissionResponse]] = {}
    for permission in permissions:
        grouped.setdefault(permission.domain, []).append(
            permission_response(permission)
        )
    return grouped


@router.get("/users", response_model=list[UserResponse])
def list_users(
    _: Annotated[AuthUser, Depends(require_permission("user.read"))],
    session: Annotated[Session, Depends(get_session)],
) -> list[UserResponse]:
    users = list(session.scalars(select(AuthUser).order_by(AuthUser.email)))
    return [build_user_response(session, user) for user in users]


@router.get("/users/{user_id}", response_model=UserResponse)
def user_details(
    user_id: UUID,
    _: Annotated[AuthUser, Depends(require_permission("user.read"))],
    session: Annotated[Session, Depends(get_session)],
) -> UserResponse:
    return build_user_response(session, get_user_or_404(session, user_id))


@router.patch("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: UUID,
    payload: UpdateUserRequest,
    current_user: Annotated[AuthUser, Depends(require_permission("user.update"))],
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> UserResponse:
    user = get_user_or_404(session, user_id)
    before = {"is_active": user.is_active, "is_verified": user.is_verified}
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.is_verified is not None:
        user.is_verified = payload.is_verified
    user.role_version += 1
    write_audit_event(
        session=session,
        actor=current_user,
        action="user.updated",
        object_type="auth_user",
        object_id=str(user.id),
        before=before,
        after={"is_active": user.is_active, "is_verified": user.is_verified},
        **audit_metadata(request),
    )
    session.commit()
    session.refresh(user)
    return build_user_response(session, user)


@router.post("/users/{user_id}/block", response_model=UserResponse)
def block_user(
    user_id: UUID,
    current_user: Annotated[AuthUser, Depends(require_permission("user.block"))],
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> UserResponse:
    user = get_user_or_404(session, user_id)
    user.is_active = False
    user.role_version += 1
    write_audit_event(
        session=session,
        actor=current_user,
        action="user.blocked",
        object_type="auth_user",
        object_id=str(user.id),
        **audit_metadata(request),
    )
    session.commit()
    session.refresh(user)
    return build_user_response(session, user)


@router.post("/users/{user_id}/unblock", response_model=UserResponse)
def unblock_user(
    user_id: UUID,
    current_user: Annotated[AuthUser, Depends(require_permission("user.block"))],
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> UserResponse:
    user = get_user_or_404(session, user_id)
    user.is_active = True
    user.role_version += 1
    write_audit_event(
        session=session,
        actor=current_user,
        action="user.unblocked",
        object_type="auth_user",
        object_id=str(user.id),
        **audit_metadata(request),
    )
    session.commit()
    session.refresh(user)
    return build_user_response(session, user)


@router.post("/users/{user_id}/roles", response_model=UserResponse)
def assign_user_role(
    user_id: UUID,
    payload: AssignRoleRequest,
    current_user: Annotated[AuthUser, Depends(require_permission("role.assign"))],
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> UserResponse:
    user = get_user_or_404(session, user_id)
    role = get_role_or_404(session, payload.role_code)
    assigned = assign_roles_to_user(
        session=session,
        user=user,
        role_codes=[role.code],
        assigned_by=current_user,
        reason=payload.reason,
    )
    if assigned:
        write_audit_event(
            session=session,
            actor=current_user,
            action="role.assigned",
            object_type="auth_user_role",
            object_id=str(user.id),
            after={"user": user.email, "role": role.code},
            **audit_metadata(request),
        )
    session.commit()
    session.refresh(user)
    return build_user_response(session, user)


@router.delete("/users/{user_id}/roles/{role_code}", response_model=UserResponse)
def revoke_user_role(
    user_id: UUID,
    role_code: str,
    current_user: Annotated[AuthUser, Depends(require_permission("role.revoke"))],
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> UserResponse:
    user = get_user_or_404(session, user_id)
    revoked = revoke_role_from_user(session=session, user=user, role_code=role_code)
    if revoked:
        write_audit_event(
            session=session,
            actor=current_user,
            action="role.revoked",
            object_type="auth_user_role",
            object_id=str(user.id),
            before={"user": user.email, "role": role_code},
            **audit_metadata(request),
        )
    session.commit()
    session.refresh(user)
    return build_user_response(session, user)


@router.get("/role-requests", response_model=list[RoleRequestResponse])
def list_role_requests(
    _: Annotated[AuthUser, Depends(require_permission("role.request.read"))],
    session: Annotated[Session, Depends(get_session)],
) -> list[RoleRequestResponse]:
    requests = list(
        session.scalars(
            select(AuthRoleRequest).order_by(AuthRoleRequest.created_at.desc())
        )
    )
    return [
        build_role_request_response(session, role_request) for role_request in requests
    ]


@router.get("/role-requests/{request_id}", response_model=RoleRequestResponse)
def role_request_details(
    request_id: UUID,
    _: Annotated[AuthUser, Depends(require_permission("role.request.read"))],
    session: Annotated[Session, Depends(get_session)],
) -> RoleRequestResponse:
    role_request = session.get(AuthRoleRequest, request_id)
    if role_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Role request not found"
        )
    return build_role_request_response(session, role_request)


@router.post("/role-requests/{request_id}/approve", response_model=RoleRequestResponse)
def approve_role_request(
    request_id: UUID,
    payload: RoleRequestDecisionRequest,
    current_user: Annotated[
        AuthUser, Depends(require_permission("role.request.approve"))
    ],
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> RoleRequestResponse:
    role_request = session.get(AuthRoleRequest, request_id)
    if role_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Role request not found"
        )
    if role_request.status != ROLE_REQUEST_PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending requests can be approved",
        )

    requester = get_user_or_404(session, role_request.requester_id)
    role = session.get(AuthRole, role_request.requested_role_id)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Role not found"
        )

    assign_roles_to_user(
        session=session,
        user=requester,
        role_codes=[role.code],
        assigned_by=current_user,
        reason=f"Approved role request {role_request.id}",
    )
    role_request.status = ROLE_REQUEST_APPROVED
    role_request.decision_comment = payload.comment
    role_request.decided_by = current_user.id
    role_request.decided_at = datetime.now(UTC)
    role_request.updated_at = datetime.now(UTC)
    write_audit_event(
        session=session,
        actor=current_user,
        action="role.request.approved",
        object_type="auth_role_request",
        object_id=str(role_request.id),
        after={"requester": requester.email, "role": role.code},
        **audit_metadata(request),
    )
    session.commit()
    session.refresh(role_request)
    return build_role_request_response(session, role_request)


@router.post("/role-requests/{request_id}/reject", response_model=RoleRequestResponse)
def reject_role_request(
    request_id: UUID,
    payload: RoleRequestDecisionRequest,
    current_user: Annotated[
        AuthUser, Depends(require_permission("role.request.reject"))
    ],
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> RoleRequestResponse:
    role_request = session.get(AuthRoleRequest, request_id)
    if role_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Role request not found"
        )
    if role_request.status != ROLE_REQUEST_PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending requests can be rejected",
        )

    role_request.status = ROLE_REQUEST_REJECTED
    role_request.decision_comment = payload.comment
    role_request.decided_by = current_user.id
    role_request.decided_at = datetime.now(UTC)
    role_request.updated_at = datetime.now(UTC)
    write_audit_event(
        session=session,
        actor=current_user,
        action="role.request.rejected",
        object_type="auth_role_request",
        object_id=str(role_request.id),
        after={"comment": payload.comment},
        **audit_metadata(request),
    )
    session.commit()
    session.refresh(role_request)
    return build_role_request_response(session, role_request)


@router.get("/audit/auth", response_model=list[AuditEventResponse])
def auth_audit(
    _: Annotated[AuthUser, Depends(require_permission("audit.auth.read"))],
    session: Annotated[Session, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[AuditEventResponse]:
    events = list(
        session.scalars(
            select(AuthAuditLog)
            .where(AuthAuditLog.action.like("auth.%"))
            .order_by(AuthAuditLog.created_at.desc())
            .limit(limit)
        )
    )
    return [AuditEventResponse.model_validate(event) for event in events]


@router.get("/audit/roles", response_model=list[AuditEventResponse])
def role_audit(
    _: Annotated[AuthUser, Depends(require_permission("audit.role.read"))],
    session: Annotated[Session, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[AuditEventResponse]:
    events = list(
        session.scalars(
            select(AuthAuditLog)
            .where(
                AuthAuditLog.action.like("role.%") | AuthAuditLog.action.like("user.%")
            )
            .order_by(AuthAuditLog.created_at.desc())
            .limit(limit)
        )
    )
    return [AuditEventResponse.model_validate(event) for event in events]
