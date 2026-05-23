from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from its.authz.context import AuthContext
from its.authz.errors import forbidden_error, unauthorized_error
from its.authz.jwt import decode_access_context
from its.tech_system.auth.security import AuthTokenError

bearer_scheme = HTTPBearer(auto_error=False)


def get_auth_context(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> AuthContext:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized_error()
    try:
        return decode_access_context(credentials.credentials)
    except AuthTokenError:
        raise unauthorized_error() from None


def require_permissions(*permissions: str):
    def dependency(
        context: Annotated[AuthContext, Depends(get_auth_context)],
    ) -> AuthContext:
        missing = [
            permission
            for permission in permissions
            if not context.has_permission(permission)
        ]
        if missing:
            raise forbidden_error(required_permissions=missing)
        return context

    return dependency


def require_any_permission(*permissions: str):
    def dependency(
        context: Annotated[AuthContext, Depends(get_auth_context)],
    ) -> AuthContext:
        if not context.has_any_permission(tuple(permissions)):
            raise forbidden_error(required_permissions=list(permissions))
        return context

    return dependency


def require_roles(*roles: str):
    def dependency(
        context: Annotated[AuthContext, Depends(get_auth_context)],
    ) -> AuthContext:
        missing = [role for role in roles if not context.has_role(role)]
        if missing:
            raise forbidden_error(required_roles=missing)
        return context

    return dependency


def require_any_role(*roles: str):
    def dependency(
        context: Annotated[AuthContext, Depends(get_auth_context)],
    ) -> AuthContext:
        if not context.has_any_role(tuple(roles)):
            raise forbidden_error(required_roles=list(roles))
        return context

    return dependency
