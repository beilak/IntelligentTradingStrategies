from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException
from t_tech.invest import AsyncClient
from t_tech.invest.exceptions import AioRequestError, InvestError

from its.execution.config import ExecutionAccountConfig, load_execution_settings
from its.execution.schemas import OrderTicket, StopOrderTicket
from its.execution.serialization import serialize_sdk_value


@dataclass(frozen=True)
class AccountReference:
    account_id: str
    name: str | None = None


class ExecutionService:
    def __init__(self) -> None:
        self.settings = load_execution_settings()

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "broker": "t-invest",
            "token_configured": self.settings.token_configured,
            "configured_accounts": len(self.settings.accounts),
            "order_submission_mode": "stub",
        }

    async def list_accounts(self) -> dict[str, Any]:
        token = self._require_token()
        configured = self._require_configured_accounts()
        try:
            async with AsyncClient(token) as client:
                response = await client.users.get_accounts()
                broker_accounts = {account.id: account for account in response.accounts}
        except (AioRequestError, InvestError) as error:
            raise self._broker_error(error) from error

        items = [
            self._build_account_item(config, broker_accounts.get(config.account_id))
            for config in configured
        ]
        return {
            "items": items,
            "total": len(items),
            "broker_accounts_total": len(broker_accounts),
            "configuration": {
                "source": "env",
                "account_ids": [account.account_id for account in configured],
            },
        }

    async def get_account_overview(
        self,
        account_id: str,
        *,
        operations_days: int = 30,
    ) -> dict[str, Any]:
        account_ref = self._require_account(account_id)
        token = self._require_token()
        now = datetime.now(UTC)
        operations_from = now - timedelta(days=operations_days)
        sections: dict[str, Any] = {}
        errors: dict[str, str] = {}

        try:
            async with AsyncClient(token) as client:
                account_response = await client.users.get_accounts()
                broker_accounts = {
                    account.id: account for account in account_response.accounts
                }
                account = broker_accounts.get(account_id)
                if account is None:
                    raise HTTPException(
                        status_code=404,
                        detail="Configured account was not returned by T-Invest.",
                    )

                sections["account"] = self._build_account_item(
                    ExecutionAccountConfig(account_ref.account_id, account_ref.name),
                    account,
                )
                sections["user_info"] = await self._safe_call(
                    "user_info",
                    client.users.get_info,
                    errors,
                )
                sections["portfolio"] = await self._safe_call(
                    "portfolio",
                    client.operations.get_portfolio,
                    errors,
                    account_id=account_id,
                )
                sections["positions"] = await self._safe_call(
                    "positions",
                    client.operations.get_positions,
                    errors,
                    account_id=account_id,
                )
                sections["withdraw_limits"] = await self._safe_call(
                    "withdraw_limits",
                    client.operations.get_withdraw_limits,
                    errors,
                    account_id=account_id,
                )
                sections["margin"] = await self._safe_call(
                    "margin",
                    client.users.get_margin_attributes,
                    errors,
                    account_id=account_id,
                )
                sections["orders"] = await self._safe_call(
                    "orders",
                    client.orders.get_orders,
                    errors,
                    account_id=account_id,
                )
                sections["stop_orders"] = await self._safe_call(
                    "stop_orders",
                    client.stop_orders.get_stop_orders,
                    errors,
                    account_id=account_id,
                )
                sections["operations"] = await self._safe_call(
                    "operations",
                    client.operations.get_operations,
                    errors,
                    account_id=account_id,
                    from_=operations_from,
                    to=now,
                )
        except HTTPException:
            raise
        except (AioRequestError, InvestError) as error:
            raise self._broker_error(error) from error

        return {
            "account_id": account_id,
            "broker": "t-invest",
            "as_of": now.isoformat(),
            "order_submission_mode": "stub",
            "operations_window": {
                "from": operations_from.isoformat(),
                "to": now.isoformat(),
                "days": operations_days,
            },
            "summary": build_account_summary(sections),
            "sections": sections,
            "section_errors": errors,
        }

    def create_order_stub(
        self,
        account_id: str,
        ticket: OrderTicket,
    ) -> dict[str, Any]:
        account = self._require_account(account_id)
        now = datetime.now(UTC)
        return {
            "id": f"stub-order-{uuid.uuid4().hex[:12]}",
            "broker": "t-invest",
            "account_id": account.account_id,
            "account_name": account.name,
            "created_at": now.isoformat(),
            "status": "accepted_by_stub",
            "submission_mode": "stub",
            "would_submit": False,
            "message": "Order ticket validated locally. No request was sent to T-Invest.",
            "ticket": ticket.model_dump(mode="json"),
        }

    def create_stop_order_stub(
        self,
        account_id: str,
        ticket: StopOrderTicket,
    ) -> dict[str, Any]:
        account = self._require_account(account_id)
        now = datetime.now(UTC)
        return {
            "id": f"stub-stop-{uuid.uuid4().hex[:12]}",
            "broker": "t-invest",
            "account_id": account.account_id,
            "account_name": account.name,
            "created_at": now.isoformat(),
            "status": "accepted_by_stub",
            "submission_mode": "stub",
            "would_submit": False,
            "message": "Stop order ticket validated locally. No request was sent to T-Invest.",
            "ticket": ticket.model_dump(mode="json"),
        }

    async def _safe_call(
        self,
        section: str,
        call,
        errors: dict[str, str],
        **kwargs: Any,
    ) -> Any:
        try:
            return serialize_sdk_value(await call(**kwargs))
        except (AioRequestError, InvestError) as error:
            errors[section] = str(error)
            return None

    def _require_token(self) -> str:
        if not self.settings.token:
            raise HTTPException(
                status_code=503,
                detail=(
                    "T-Invest token is not configured. Set EXECUTION_TINVEST_TOKEN, "
                    "tinvest_token, TINVEST_TOKEN or TINKOFF_INVEST_API_TOKEN."
                ),
            )
        return self.settings.token

    def _require_configured_accounts(self) -> tuple[ExecutionAccountConfig, ...]:
        if not self.settings.accounts:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Execution accounts are not configured. Set "
                    "EXECUTION_TINVEST_ACCOUNTS or EXECUTION_TINVEST_ACCOUNT_IDS."
                ),
            )
        return self.settings.accounts

    def _require_account(self, account_id: str) -> AccountReference:
        configured = self._require_configured_accounts()
        for account in configured:
            if account.account_id == account_id:
                return AccountReference(account_id=account.account_id, name=account.name)
        raise HTTPException(
            status_code=404,
            detail="Account is not configured for execution.",
        )

    def _build_account_item(
        self,
        config: ExecutionAccountConfig,
        account: Any | None,
    ) -> dict[str, Any]:
        if account is None:
            return {
                "id": config.account_id,
                "name": config.name or mask_account_id(config.account_id),
                "broker_name": None,
                "type": None,
                "status": "NOT_RETURNED_BY_BROKER",
                "access_level": None,
                "opened_date": None,
                "closed_date": None,
                "is_configured": True,
                "is_available": False,
            }

        payload = serialize_sdk_value(account)
        payload["broker_name"] = payload.get("name")
        payload["name"] = config.name or payload.get("name") or mask_account_id(account.id)
        payload["is_configured"] = True
        payload["is_available"] = True
        return payload

    @staticmethod
    def _broker_error(error: Exception) -> HTTPException:
        return HTTPException(
            status_code=502,
            detail=f"T-Invest request failed: {error}",
        )


def build_account_summary(sections: dict[str, Any]) -> dict[str, Any]:
    portfolio = sections.get("portfolio") or {}
    positions = sections.get("positions") or {}
    orders = sections.get("orders") or {}
    stop_orders = sections.get("stop_orders") or {}
    operations = sections.get("operations") or {}

    portfolio_positions = portfolio.get("positions") or []
    position_rows = positions.get("securities") or []
    money_rows = positions.get("money") or []
    blocked_money_rows = positions.get("blocked") or []

    total_portfolio = portfolio.get("total_amount_portfolio")
    expected_yield = portfolio.get("expected_yield")
    daily_yield = portfolio.get("daily_yield")
    daily_yield_relative = portfolio.get("daily_yield_relative")

    return {
        "total_amount_portfolio": total_portfolio,
        "expected_yield": expected_yield,
        "daily_yield": daily_yield,
        "daily_yield_relative": daily_yield_relative,
        "portfolio_value": _extract_value(total_portfolio),
        "expected_yield_value": _extract_value(expected_yield),
        "daily_yield_value": _extract_value(daily_yield),
        "daily_yield_relative_value": _extract_value(daily_yield_relative),
        "portfolio_positions_count": len(portfolio_positions),
        "securities_count": len(position_rows),
        "money": money_rows,
        "blocked_money": blocked_money_rows,
        "open_orders_count": len(orders.get("orders") or []),
        "stop_orders_count": len(stop_orders.get("stop_orders") or []),
        "operations_count": len(operations.get("operations") or []),
        "allocation": build_allocation(portfolio),
    }


def build_allocation(portfolio: dict[str, Any]) -> list[dict[str, Any]]:
    buckets = [
        ("shares", portfolio.get("total_amount_shares")),
        ("bonds", portfolio.get("total_amount_bonds")),
        ("etf", portfolio.get("total_amount_etf")),
        ("currencies", portfolio.get("total_amount_currencies")),
        ("futures", portfolio.get("total_amount_futures")),
        ("options", portfolio.get("total_amount_options")),
        ("structured_products", portfolio.get("total_amount_sp")),
        ("dfa", portfolio.get("total_amount_dfa")),
    ]
    return [
        {"bucket": bucket, "amount": amount, "value": _extract_value(amount)}
        for bucket, amount in buckets
        if _extract_value(amount) not in (None, 0)
    ]


def mask_account_id(account_id: str) -> str:
    if len(account_id) <= 6:
        return account_id
    return f"...{account_id[-6:]}"


def _extract_value(value: Any) -> float | None:
    if not value:
        return None
    if isinstance(value, dict) and isinstance(value.get("value"), int | float):
        return float(value["value"])
    return None


__all__ = [
    "ExecutionService",
    "build_account_summary",
    "build_allocation",
    "mask_account_id",
]
