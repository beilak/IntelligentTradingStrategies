from dataclasses import dataclass
from uuid import NAMESPACE_URL, UUID, uuid5


@dataclass(frozen=True)
class PermissionSeed:
    code: str
    title: str
    description: str = ""
    is_critical: bool = False

    @property
    def id(self) -> UUID:
        return stable_permission_id(self.code)

    @property
    def domain(self) -> str:
        return self.code.split(".")[0]

    @property
    def resource(self) -> str:
        parts = self.code.split(".")
        return parts[1] if len(parts) > 1 else self.code

    @property
    def action(self) -> str:
        parts = self.code.split(".")
        return ".".join(parts[2:]) if len(parts) > 2 else "execute"


@dataclass(frozen=True)
class RoleSeed:
    code: str
    title: str
    description: str
    permission_codes: tuple[str, ...]
    is_system: bool = True
    is_assignable: bool = True

    @property
    def id(self) -> UUID:
        return stable_role_id(self.code)


def stable_permission_id(code: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"its:auth:permission:{code}")


def stable_role_id(code: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"its:auth:role:{code}")


def stable_role_permission_id(role_code: str, permission_code: str) -> UUID:
    return uuid5(
        NAMESPACE_URL, f"its:auth:role_permission:{role_code}:{permission_code}"
    )


PERMISSIONS: tuple[PermissionSeed, ...] = (
    PermissionSeed("app.launchpad.read", "Launchpad"),
    PermissionSeed("app.docs.read", "Documentation"),
    PermissionSeed("profile.self.read", "Read own profile"),
    PermissionSeed("profile.self.update", "Update own profile"),
    PermissionSeed("data.sources.read", "Read data sources"),
    PermissionSeed("data.instruments.read", "Read instruments"),
    PermissionSeed("data.prices.read", "Read prices"),
    PermissionSeed("data.dividends.read", "Read dividends"),
    PermissionSeed("data.custom_bars.read", "Read custom bars"),
    PermissionSeed("data.upload.create", "Create data upload"),
    PermissionSeed("data.upload.read", "Read data uploads"),
    PermissionSeed(
        "data.version.deactivate", "Deactivate data version", is_critical=True
    ),
    PermissionSeed("data.source.create", "Create data source"),
    PermissionSeed("data.source.update", "Update data source"),
    PermissionSeed("strategy.component.read", "Read strategy components"),
    PermissionSeed("strategy.component.create", "Create strategy component"),
    PermissionSeed("strategy.component.update", "Update strategy component"),
    PermissionSeed(
        "strategy.component.delete", "Delete strategy component", is_critical=True
    ),
    PermissionSeed("strategy.model.read", "Read strategy models"),
    PermissionSeed("strategy.model.create", "Create strategy model"),
    PermissionSeed("strategy.model.update", "Update strategy model"),
    PermissionSeed("strategy.model.delete", "Delete strategy model", is_critical=True),
    PermissionSeed("strategy.test.run", "Run strategy tests"),
    PermissionSeed("strategy.test.read", "Read strategy test results"),
    PermissionSeed("strategy.compare.read", "Compare strategies"),
    PermissionSeed("strategy.production.request", "Request strategy production export"),
    PermissionSeed("ga.alphabet.read", "Read GA alphabets"),
    PermissionSeed("ga.alphabet.update", "Update GA alphabets"),
    PermissionSeed("ga.run.create", "Create GA run"),
    PermissionSeed("ga.run.read", "Read GA runs"),
    PermissionSeed("ga.run.cancel", "Cancel GA run"),
    PermissionSeed("ga.candidate.materialize", "Materialize GA candidate"),
    PermissionSeed("production.strategy.request", "Create production strategy request"),
    PermissionSeed("production.strategy.read", "Read production strategies"),
    PermissionSeed(
        "production.strategy.approve", "Approve production strategy", is_critical=True
    ),
    PermissionSeed("production.strategy.reject", "Reject production strategy"),
    PermissionSeed(
        "production.strategy.deploy", "Deploy production strategy", is_critical=True
    ),
    PermissionSeed(
        "production.strategy.disable", "Disable production strategy", is_critical=True
    ),
    PermissionSeed("trading.paper.start", "Start paper trading"),
    PermissionSeed("trading.paper.stop", "Stop paper trading"),
    PermissionSeed("trading.live.start", "Start live trading", is_critical=True),
    PermissionSeed("trading.live.stop", "Stop live trading", is_critical=True),
    PermissionSeed("trading.orders.read", "Read trading orders"),
    PermissionSeed("trading.trades.read", "Read trades"),
    PermissionSeed("trading.positions.read", "Read positions"),
    PermissionSeed(
        "trading.emergency_stop", "Emergency stop trading", is_critical=True
    ),
    PermissionSeed("risk.limits.read", "Read risk limits"),
    PermissionSeed("risk.limits.update", "Update risk limits", is_critical=True),
    PermissionSeed("risk.events.read", "Read risk events"),
    PermissionSeed("risk.strategy.approve", "Risk approve strategy", is_critical=True),
    PermissionSeed("risk.strategy.block", "Block strategy by risk", is_critical=True),
    PermissionSeed("secret.reference.read", "Read secret references"),
    PermissionSeed(
        "secret.reference.create", "Create secret reference", is_critical=True
    ),
    PermissionSeed(
        "secret.reference.update", "Update secret reference", is_critical=True
    ),
    PermissionSeed(
        "secret.reference.delete", "Delete secret reference", is_critical=True
    ),
    PermissionSeed(
        "secret.reference.rotate", "Rotate secret reference", is_critical=True
    ),
    PermissionSeed("broker.account.read", "Read broker accounts"),
    PermissionSeed("broker.account.create", "Create broker account", is_critical=True),
    PermissionSeed("broker.account.update", "Update broker account", is_critical=True),
    PermissionSeed("user.read", "Read users"),
    PermissionSeed("user.update", "Update users"),
    PermissionSeed("user.block", "Block users", is_critical=True),
    PermissionSeed("role.read", "Read roles"),
    PermissionSeed("role.create", "Create role", is_critical=True),
    PermissionSeed("role.update", "Update role", is_critical=True),
    PermissionSeed("role.delete", "Delete role", is_critical=True),
    PermissionSeed("role.assign", "Assign role", is_critical=True),
    PermissionSeed("role.revoke", "Revoke role", is_critical=True),
    PermissionSeed("role.request.create", "Create role request"),
    PermissionSeed("role.request.read", "Read role requests"),
    PermissionSeed("role.request.approve", "Approve role request", is_critical=True),
    PermissionSeed("role.request.reject", "Reject role request"),
    PermissionSeed("permission.read", "Read permissions"),
    PermissionSeed("audit.auth.read", "Read auth audit"),
    PermissionSeed("audit.role.read", "Read role audit"),
    PermissionSeed("audit.production.read", "Read production audit"),
    PermissionSeed("audit.trading.read", "Read trading audit"),
    PermissionSeed("audit.secret.read", "Read secret audit"),
    PermissionSeed("system.health.read", "Read system health"),
    PermissionSeed("system.settings.read", "Read system settings"),
    PermissionSeed(
        "system.settings.update", "Update system settings", is_critical=True
    ),
    PermissionSeed("system.logs.read", "Read system logs"),
    PermissionSeed(
        "system.integrations.manage", "Manage system integrations", is_critical=True
    ),
)

PERMISSION_CODES = tuple(permission.code for permission in PERMISSIONS)
PERMISSIONS_BY_CODE = {permission.code: permission for permission in PERMISSIONS}

COMMON_PERMISSIONS = (
    "app.launchpad.read",
    "app.docs.read",
    "profile.self.read",
    "role.request.create",
)
DOCUMENTATION_READER_PERMISSIONS = (
    "app.launchpad.read",
    "app.docs.read",
    "profile.self.read",
    "role.request.create",
)
DATA_READ_PERMISSIONS = (
    "data.sources.read",
    "data.instruments.read",
    "data.prices.read",
    "data.dividends.read",
    "data.custom_bars.read",
)
STRATEGY_READ_PERMISSIONS = (
    "strategy.component.read",
    "strategy.model.read",
    "strategy.test.read",
    "strategy.compare.read",
)
GA_READ_PERMISSIONS = ("ga.alphabet.read", "ga.run.read")
PRODUCTION_READ_PERMISSIONS = ("production.strategy.read",)
TRADING_READ_PERMISSIONS = (
    "trading.orders.read",
    "trading.trades.read",
    "trading.positions.read",
)
AUDIT_READ_PERMISSIONS = (
    "audit.auth.read",
    "audit.role.read",
    "audit.production.read",
    "audit.trading.read",
    "audit.secret.read",
)


def merge_permissions(*groups: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for group in groups:
        for permission in group:
            if permission not in seen:
                seen.add(permission)
                result.append(permission)
    return tuple(result)


ROLES: tuple[RoleSeed, ...] = (
    RoleSeed(
        code="documentation_reader",
        title="Documentation Reader",
        description="Initial account access for documentation and access requests only.",
        permission_codes=DOCUMENTATION_READER_PERMISSIONS,
    ),
    RoleSeed(
        code="viewer",
        title="Viewer",
        description="Read-only access to platform workspace and reports.",
        permission_codes=merge_permissions(
            COMMON_PERMISSIONS,
            DATA_READ_PERMISSIONS,
            STRATEGY_READ_PERMISSIONS,
            GA_READ_PERMISSIONS,
        ),
    ),
    RoleSeed(
        code="quant_researcher",
        title="Quant Researcher",
        description="Researcher role for hypotheses, strategy components, tests and GA runs.",
        permission_codes=merge_permissions(
            COMMON_PERMISSIONS,
            DATA_READ_PERMISSIONS,
            STRATEGY_READ_PERMISSIONS,
            GA_READ_PERMISSIONS,
            (
                "strategy.component.create",
                "strategy.component.update",
                "strategy.model.create",
                "strategy.model.update",
                "strategy.test.run",
                "ga.run.create",
                "ga.run.cancel",
                "ga.candidate.materialize",
                "strategy.production.request",
            ),
        ),
    ),
    RoleSeed(
        code="data_manager",
        title="Data Manager",
        description="Manages data loading, sources and data version visibility.",
        permission_codes=merge_permissions(
            COMMON_PERMISSIONS,
            DATA_READ_PERMISSIONS,
            (
                "data.upload.create",
                "data.upload.read",
                "data.version.deactivate",
                "data.source.create",
                "data.source.update",
            ),
        ),
    ),
    RoleSeed(
        code="strategy_releaser",
        title="Strategy Releaser",
        description="Prepares strategy production export requests.",
        permission_codes=merge_permissions(
            COMMON_PERMISSIONS,
            STRATEGY_READ_PERMISSIONS,
            PRODUCTION_READ_PERMISSIONS,
            ("strategy.production.request", "production.strategy.request"),
        ),
    ),
    RoleSeed(
        code="production_approver",
        title="Production Approver",
        description="Reviews and approves or rejects production strategy requests.",
        permission_codes=merge_permissions(
            COMMON_PERMISSIONS,
            PRODUCTION_READ_PERMISSIONS,
            ("production.strategy.approve", "production.strategy.reject"),
        ),
    ),
    RoleSeed(
        code="trading_operator",
        title="Trading Operator",
        description="Operates paper and approved live trading runs without reading secrets.",
        permission_codes=merge_permissions(
            COMMON_PERMISSIONS,
            PRODUCTION_READ_PERMISSIONS,
            TRADING_READ_PERMISSIONS,
            (
                "trading.paper.start",
                "trading.paper.stop",
                "trading.live.start",
                "trading.live.stop",
            ),
        ),
    ),
    RoleSeed(
        code="risk_manager",
        title="Risk Manager",
        description="Manages risk limits, live approvals and emergency stops.",
        permission_codes=merge_permissions(
            COMMON_PERMISSIONS,
            PRODUCTION_READ_PERMISSIONS,
            (
                "risk.limits.read",
                "risk.limits.update",
                "risk.events.read",
                "risk.strategy.approve",
                "risk.strategy.block",
                "trading.emergency_stop",
                "production.strategy.reject",
                "audit.trading.read",
            ),
        ),
    ),
    RoleSeed(
        code="secret_manager",
        title="Secret Manager",
        description="Manages secret references without reading secret values.",
        permission_codes=merge_permissions(
            COMMON_PERMISSIONS,
            (
                "secret.reference.read",
                "secret.reference.create",
                "secret.reference.update",
                "secret.reference.delete",
                "secret.reference.rotate",
                "broker.account.read",
                "broker.account.create",
                "broker.account.update",
                "audit.secret.read",
            ),
        ),
    ),
    RoleSeed(
        code="role_admin",
        title="Role Admin",
        description="Manages users, roles, permissions and role requests.",
        permission_codes=merge_permissions(
            COMMON_PERMISSIONS,
            (
                "user.read",
                "user.update",
                "user.block",
                "role.read",
                "role.create",
                "role.update",
                "role.delete",
                "role.assign",
                "role.revoke",
                "role.request.read",
                "role.request.approve",
                "role.request.reject",
                "permission.read",
                "audit.role.read",
            ),
        ),
    ),
    RoleSeed(
        code="system_admin",
        title="System Admin",
        description="Manages technical platform state without implicit production approval.",
        permission_codes=merge_permissions(
            COMMON_PERMISSIONS,
            (
                "system.health.read",
                "system.settings.read",
                "system.settings.update",
                "system.logs.read",
                "system.integrations.manage",
                "user.read",
                "audit.auth.read",
                "audit.role.read",
            ),
        ),
    ),
    RoleSeed(
        code="auditor",
        title="Auditor",
        description="Read-only access to audit trails and authorization history.",
        permission_codes=merge_permissions(
            COMMON_PERMISSIONS,
            AUDIT_READ_PERMISSIONS,
            ("user.read", "role.read", "permission.read", "production.strategy.read"),
        ),
    ),
)

ROLES_BY_CODE = {role.code: role for role in ROLES}
DEFAULT_ROLE_CODE = "documentation_reader"
BOOTSTRAP_ADMIN_ROLE_CODES = ("system_admin", "role_admin")
