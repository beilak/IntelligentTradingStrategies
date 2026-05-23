from fastapi import HTTPException, status


def unauthorized_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "error": "unauthorized",
            "message": "Authentication token is missing or invalid.",
        },
        headers={"WWW-Authenticate": "Bearer"},
    )


def forbidden_error(
    *,
    required_permissions: list[str] | None = None,
    required_roles: list[str] | None = None,
) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "error": "forbidden",
            "message": "You do not have permission to perform this action.",
            "required_permissions": required_permissions or [],
            "required_roles": required_roles or [],
        },
    )
