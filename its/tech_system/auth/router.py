from datetime import UTC, datetime
from collections.abc import Mapping
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from its.db.models import AuthUser
from its.db.session import get_session
from its.tech_system.auth.schemas import (
    AuthResponse,
    LoginRequest,
    LogoutResponse,
    RefreshTokenRequest,
    RegisterRequest,
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

router = APIRouter()
bearer_scheme = HTTPBearer(auto_error=False)


def auth_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_user_by_email(session: Session, email: str) -> AuthUser | None:
    return session.scalar(select(AuthUser).where(AuthUser.email == email))


def build_auth_response(user: AuthUser) -> AuthResponse:
    access_token, expires_in = create_jwt_token(
        subject=user.id,
        email=user.email,
        role_version=user.role_version,
        token_type="access",
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
        user=UserResponse.model_validate(user),
    )


def token_role_version_matches(payload: Mapping[str, object], user: AuthUser) -> bool:
    try:
        return int(payload.get("role_version", -1)) == user.role_version
    except (TypeError, ValueError):
        return False


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
    if (
        user is None
        or not user.is_active
        or not token_role_version_matches(payload, user)
    ):
        raise auth_exception()
    return user


@router.post(
    "/auth/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED
)
def register(
    payload: RegisterRequest, session: Annotated[Session, Depends(get_session)]
) -> AuthResponse:
    if get_user_by_email(session, payload.email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="User already exists"
        )

    user = AuthUser(email=payload.email, password_hash=hash_password(payload.password))
    session.add(user)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="User already exists"
        ) from None
    session.refresh(user)
    return build_auth_response(user)


@router.post("/auth/login", response_model=AuthResponse)
def login(
    payload: LoginRequest, session: Annotated[Session, Depends(get_session)]
) -> AuthResponse:
    user = get_user_by_email(session, payload.email)
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="User is disabled"
        )

    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)
    user.last_login_at = datetime.now(UTC)
    session.commit()
    session.refresh(user)
    return build_auth_response(user)


@router.post("/auth/refresh", response_model=AuthResponse)
def refresh(
    payload: RefreshTokenRequest, session: Annotated[Session, Depends(get_session)]
) -> AuthResponse:
    try:
        token_payload = decode_jwt_token(payload.refresh_token, expected_type="refresh")
        user_id = UUID(str(token_payload["sub"]))
    except (AuthTokenError, KeyError, ValueError):
        raise auth_exception() from None

    user = session.get(AuthUser, user_id)
    if (
        user is None
        or not user.is_active
        or not token_role_version_matches(token_payload, user)
    ):
        raise auth_exception()
    return build_auth_response(user)


@router.get("/auth/me", response_model=UserResponse)
def me(current_user: Annotated[AuthUser, Depends(get_current_user)]) -> AuthUser:
    return current_user


@router.post("/auth/logout", response_model=LogoutResponse)
def logout(_: Annotated[AuthUser, Depends(get_current_user)]) -> LogoutResponse:
    return LogoutResponse(status="ok")
