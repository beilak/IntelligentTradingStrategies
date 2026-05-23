from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from its.authz.context import AuthContext
from its.authz.jwt import decode_access_context
from its.authz.permissions import Permissions
from its.tech_system.auth.security import AuthTokenError

bearer_scheme = HTTPBearer(auto_error=False)


def event_log_auth_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_event_log_access_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> AuthContext:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise event_log_auth_exception()
    try:
        context = decode_access_context(credentials.credentials)
    except AuthTokenError:
        raise event_log_auth_exception() from None
    if not context.has_permission(Permissions.SYSTEM_LOGS_READ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "forbidden",
                "message": "You do not have permission to view event logs.",
                "required_permissions": [Permissions.SYSTEM_LOGS_READ],
            },
        )
    return context
