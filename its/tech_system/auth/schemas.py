from datetime import datetime
from re import compile as compile_regex
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

EMAIL_PATTERN = compile_regex(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(value: str) -> str:
    email = value.strip().lower()
    if not EMAIL_PATTERN.match(email):
        raise ValueError("Invalid email address")
    return email


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=10, max_length=256)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=20)


class RoleSummary(BaseModel):
    code: str
    title: str
    description: str | None = None

    model_config = ConfigDict(from_attributes=True)


class UserResponse(BaseModel):
    id: UUID
    email: str
    is_active: bool
    is_verified: bool
    role_version: int
    created_at: datetime
    last_login_at: datetime | None = None
    roles: list[RoleSummary] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class LogoutResponse(BaseModel):
    status: str


class RoleResponse(RoleSummary):
    is_system: bool
    is_assignable: bool
    permissions: list[str] = Field(default_factory=list)


class PermissionResponse(BaseModel):
    code: str
    domain: str
    resource: str
    action: str
    title: str
    description: str | None = None
    is_critical: bool

    model_config = ConfigDict(from_attributes=True)


class RoleAssignmentResponse(BaseModel):
    role: RoleSummary
    assigned_at: datetime
    assigned_by: UUID | None = None
    expires_at: datetime | None = None
    reason: str | None = None


class RoleRequestCreateRequest(BaseModel):
    role_code: str = Field(min_length=1, max_length=128)
    justification: str = Field(min_length=10, max_length=4000)


class RoleRequestDecisionRequest(BaseModel):
    comment: str = Field(min_length=3, max_length=4000)


class RoleRequestResponse(BaseModel):
    id: UUID
    requester_id: UUID
    requester_email: str | None = None
    role: RoleSummary
    status: str
    justification: str
    decision_comment: str | None = None
    decided_by: UUID | None = None
    decided_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AssignRoleRequest(BaseModel):
    role_code: str = Field(min_length=1, max_length=128)
    reason: str | None = Field(default=None, max_length=4000)


class UpdateUserRequest(BaseModel):
    is_active: bool | None = None
    is_verified: bool | None = None


class RoleCreateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    is_assignable: bool = True
    permission_codes: list[str] = Field(default_factory=list)


class RoleUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    is_assignable: bool | None = None
    permission_codes: list[str] | None = None


class AuditEventResponse(BaseModel):
    id: UUID
    actor_user_id: UUID | None = None
    action: str
    object_type: str
    object_id: str | None = None
    before_json: dict[str, object] | None = None
    after_json: dict[str, object] | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
