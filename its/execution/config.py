from __future__ import annotations

import json
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionAccountConfig:
    account_id: str
    name: str | None = None


@dataclass(frozen=True)
class ExecutionSettings:
    token: str | None
    accounts: tuple[ExecutionAccountConfig, ...]
    order_submission_mode: str = "real"

    @property
    def token_configured(self) -> bool:
        return bool(self.token)

    @property
    def account_ids(self) -> tuple[str, ...]:
        return tuple(account.account_id for account in self.accounts)


TOKEN_ENV_NAMES = (
    "EXECUTION_TINVEST_TOKEN",
    "tinvest_token",
    "TINVEST_TOKEN",
    "TINKOFF_INVEST_API_TOKEN",
)

ACCOUNT_LIST_ENV_NAMES = (
    "EXECUTION_TINVEST_ACCOUNTS",
    "EXECUTION_TINVEST_ACCOUNT_IDS",
    "EXECUTION_ACCOUNT_IDS",
    "TINVEST_ACCOUNT_IDS",
    "tinvest_account_ids",
)

ACCOUNT_ID_PREFIXES = (
    "EXECUTION_TINVEST_ACCOUNT_ID",
    "TINVEST_ACCOUNT_ID",
    "tinvest_account_id",
)

ORDER_SUBMISSION_MODE_ENV_NAMES = (
    "EXECUTION_ORDER_SUBMISSION_MODE",
    "EXECUTION_TINVEST_ORDER_SUBMISSION_MODE",
)

ORDER_SUBMISSION_MODE_ALIASES = {
    "broker": "real",
    "live": "real",
    "real": "real",
    "t-invest": "real",
    "tinvest": "real",
    "dry-run": "stub",
    "dry_run": "stub",
    "stub": "stub",
}


def load_execution_settings() -> ExecutionSettings:
    return ExecutionSettings(
        token=_first_env_value(TOKEN_ENV_NAMES),
        accounts=parse_account_configs(os.environ),
        order_submission_mode=parse_order_submission_mode(os.environ),
    )


def parse_account_configs(
    environ: os._Environ[str] | dict[str, str],
) -> tuple[ExecutionAccountConfig, ...]:
    raw_values: list[str] = []
    for name in ACCOUNT_LIST_ENV_NAMES:
        value = environ.get(name)
        if value:
            raw_values.append(value)

    for name in sorted(environ):
        if any(name.startswith(prefix) for prefix in ACCOUNT_ID_PREFIXES):
            value = environ.get(name)
            if value:
                raw_values.append(value)

    configs: list[ExecutionAccountConfig] = []
    for raw_value in raw_values:
        configs.extend(_parse_account_value(raw_value))

    deduped: dict[str, ExecutionAccountConfig] = {}
    for config in configs:
        if not config.account_id:
            continue
        deduped.setdefault(config.account_id, config)

    return tuple(deduped.values())


def _first_env_value(names: tuple[str, ...]) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def parse_order_submission_mode(
    environ: os._Environ[str] | dict[str, str],
) -> str:
    for name in ORDER_SUBMISSION_MODE_ENV_NAMES:
        value = environ.get(name)
        if not value:
            continue
        return ORDER_SUBMISSION_MODE_ALIASES.get(value.strip().lower(), "real")
    return "real"


def _parse_account_value(raw_value: str) -> list[ExecutionAccountConfig]:
    value = raw_value.strip()
    if not value:
        return []
    if value.startswith("["):
        return _parse_json_accounts(value)

    return [_parse_account_item(item) for item in value.split(",") if item.strip()]


def _parse_json_accounts(raw_value: str) -> list[ExecutionAccountConfig]:
    try:
        payload = json.loads(raw_value)
    except json.JSONDecodeError:
        return [_parse_account_item(raw_value)]

    if not isinstance(payload, list):
        return []

    configs: list[ExecutionAccountConfig] = []
    for item in payload:
        if isinstance(item, str):
            configs.append(_parse_account_item(item))
            continue
        if isinstance(item, dict):
            account_id = str(item.get("id") or item.get("account_id") or "").strip()
            name = item.get("name") or item.get("title") or item.get("alias")
            configs.append(
                ExecutionAccountConfig(
                    account_id=account_id,
                    name=str(name).strip() if name else None,
                )
            )
    return configs


def _parse_account_item(item: str) -> ExecutionAccountConfig:
    text = item.strip()
    for separator in ("|", "=", ":"):
        if separator in text:
            account_id, name = text.split(separator, 1)
            return ExecutionAccountConfig(
                account_id=account_id.strip(),
                name=name.strip() or None,
            )
    return ExecutionAccountConfig(account_id=text)
