from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from its.tech_system.auth.settings import AuthSettings, get_auth_settings

TokenType = Literal["access", "refresh"]

password_hasher = PasswordHasher()


class AuthTokenError(Exception):
    pass


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    try:
        return password_hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


def create_jwt_token(
    *,
    subject: UUID,
    email: str,
    role_version: int,
    token_type: TokenType,
    settings: AuthSettings | None = None,
) -> tuple[str, int]:
    auth_settings = settings or get_auth_settings()
    now = datetime.now(UTC)
    ttl = (
        timedelta(minutes=auth_settings.access_token_ttl_minutes)
        if token_type == "access"
        else timedelta(days=auth_settings.refresh_token_ttl_days)
    )
    expires_at = now + ttl
    payload: dict[str, Any] = {
        "sub": str(subject),
        "email": email,
        "typ": token_type,
        "role_version": role_version,
        "iss": auth_settings.jwt_issuer,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    token = jwt.encode(
        payload, auth_settings.jwt_secret_key, algorithm=auth_settings.jwt_algorithm
    )
    return token, int(ttl.total_seconds())


def decode_jwt_token(
    token: str,
    expected_type: TokenType,
    settings: AuthSettings | None = None,
) -> dict[str, Any]:
    auth_settings = settings or get_auth_settings()
    try:
        payload = jwt.decode(
            token,
            auth_settings.jwt_secret_key,
            algorithms=[auth_settings.jwt_algorithm],
            issuer=auth_settings.jwt_issuer,
        )
    except jwt.PyJWTError as exc:
        raise AuthTokenError("Invalid authentication token") from exc

    if payload.get("typ") != expected_type:
        raise AuthTokenError("Unexpected authentication token type")
    return payload
