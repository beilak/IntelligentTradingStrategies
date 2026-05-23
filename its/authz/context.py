from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class AuthContext:
    user_id: UUID
    email: str
    role_version: int
    roles: tuple[str, ...]
    permissions: tuple[str, ...]
    env_scopes: tuple[str, ...]

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions

    def has_any_permission(self, permissions: tuple[str, ...]) -> bool:
        return any(permission in self.permissions for permission in permissions)

    def has_role(self, role: str) -> bool:
        return role in self.roles

    def has_any_role(self, roles: tuple[str, ...]) -> bool:
        return any(role in self.roles for role in roles)
