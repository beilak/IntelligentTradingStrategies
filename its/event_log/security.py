from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from its.tech_system.auth.security import AuthTokenError, decode_jwt_token

bearer_scheme = HTTPBearer(auto_error=False)


def event_log_auth_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_event_log_access_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> dict[str, Any]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise event_log_auth_exception()
    try:
        return decode_jwt_token(credentials.credentials, expected_type="access")
    except AuthTokenError:
        raise event_log_auth_exception() from None

