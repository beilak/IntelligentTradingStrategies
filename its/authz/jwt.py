from uuid import UUID

from its.authz.context import AuthContext
from its.tech_system.auth.security import AuthTokenError, decode_jwt_token


def decode_access_context(token: str) -> AuthContext:
    payload = decode_jwt_token(token, expected_type="access")
    try:
        return AuthContext(
            user_id=UUID(str(payload["sub"])),
            email=str(payload["email"]),
            role_version=int(payload["role_version"]),
            roles=tuple(str(role) for role in payload.get("roles", [])),
            permissions=tuple(
                str(permission) for permission in payload.get("permissions", [])
            ),
            env_scopes=tuple(str(scope) for scope in payload.get("env_scopes", [])),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise AuthTokenError("Invalid authentication token payload") from exc
