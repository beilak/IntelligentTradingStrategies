from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, AsyncIterator

from fastapi import HTTPException
from t_tech.invest import (
    AsyncClient,
    ExchangeOrderType,
    OrderBookInstrument,
    OrderDirection,
    OrderType,
    PriceType,
    StopOrderDirection,
    StopOrderExpirationType,
    StopOrderType,
    TakeProfitType,
    TimeInForceType,
    utils,
)
from t_tech.invest.exceptions import AioRequestError, InvestError

from its.execution.config import ExecutionAccountConfig, load_execution_settings
from its.execution.schemas import OrderTicket, StopOrderTicket
from its.execution.serialization import serialize_quotation, serialize_sdk_value


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
            "order_submission_mode": self.settings.order_submission_mode,
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
            "order_submission_mode": self.settings.order_submission_mode,
            "operations_window": {
                "from": operations_from.isoformat(),
                "to": now.isoformat(),
                "days": operations_days,
            },
            "summary": build_account_summary(sections),
            "sections": sections,
            "section_errors": errors,
        }

    async def submit_order(
        self,
        account_id: str,
        ticket: OrderTicket,
    ) -> dict[str, Any]:
        if self.settings.order_submission_mode == "stub":
            return self.create_order_stub(account_id, ticket)
        return await self.create_order(account_id, ticket)

    async def submit_stop_order(
        self,
        account_id: str,
        ticket: StopOrderTicket,
    ) -> dict[str, Any]:
        if self.settings.order_submission_mode == "stub":
            return self.create_stop_order_stub(account_id, ticket)
        return await self.create_stop_order(account_id, ticket)

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
            "submitted": False,
            "message": "Order ticket validated locally. No request was sent to T-Invest.",
            "ticket": ticket.model_dump(mode="json"),
            "broker_response": None,
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
            "submitted": False,
            "message": "Stop order ticket validated locally. No request was sent to T-Invest.",
            "ticket": ticket.model_dump(mode="json"),
            "broker_response": None,
        }

    async def create_order(
        self,
        account_id: str,
        ticket: OrderTicket,
    ) -> dict[str, Any]:
        account = self._require_account(account_id)
        token = self._require_token()
        order_id = normalize_client_order_id(ticket.client_order_id)
        now = datetime.now(UTC)

        try:
            async with AsyncClient(token) as client:
                response = await client.orders.post_order(
                    account_id=account.account_id,
                    instrument_id=ticket.instrument_id,
                    figi=ticket.figi or "",
                    quantity=ticket.quantity,
                    price=quotation_from_float(ticket.price)
                    if ticket.order_type == "limit"
                    else None,
                    direction=order_direction(ticket.side),
                    order_type=order_type(ticket.order_type),
                    order_id=order_id,
                    time_in_force=time_in_force(ticket.time_in_force),
                    price_type=price_type(ticket.price_type),
                )
        except (AioRequestError, InvestError) as error:
            raise self._broker_error(error) from error

        payload = serialize_sdk_value(response)
        broker_order_id = payload.get("order_id") or order_id
        return {
            "id": broker_order_id,
            "broker_order_id": broker_order_id,
            "broker": "t-invest",
            "account_id": account.account_id,
            "account_name": account.name,
            "created_at": now.isoformat(),
            "status": payload.get("execution_report_status") or "submitted_to_broker",
            "submission_mode": "real",
            "would_submit": True,
            "submitted": True,
            "message": payload.get("message") or "Order was submitted to T-Invest.",
            "ticket": ticket.model_dump(mode="json"),
            "broker_response": payload,
        }

    async def create_stop_order(
        self,
        account_id: str,
        ticket: StopOrderTicket,
    ) -> dict[str, Any]:
        account = self._require_account(account_id)
        token = self._require_token()
        order_id = normalize_client_order_id(ticket.client_order_id)
        now = datetime.now(UTC)

        try:
            async with AsyncClient(token) as client:
                response = await client.stop_orders.post_stop_order(
                    account_id=account.account_id,
                    instrument_id=ticket.instrument_id,
                    figi=ticket.figi or "",
                    quantity=ticket.quantity,
                    price=quotation_from_float(ticket.limit_price),
                    stop_price=quotation_from_float(ticket.stop_price),
                    direction=stop_order_direction(ticket.side),
                    expiration_type=stop_order_expiration_type(ticket.expire_at),
                    stop_order_type=stop_order_type(ticket.stop_order_type),
                    expire_date=normalize_expire_at(ticket.expire_at),
                    exchange_order_type=exchange_order_type(ticket.limit_price),
                    take_profit_type=TakeProfitType.TAKE_PROFIT_TYPE_REGULAR,
                    price_type=price_type(ticket.price_type),
                    order_id=order_id,
                )
        except (AioRequestError, InvestError) as error:
            raise self._broker_error(error) from error

        payload = serialize_sdk_value(response)
        broker_order_id = payload.get("stop_order_id") or order_id
        return {
            "id": broker_order_id,
            "broker_order_id": broker_order_id,
            "broker": "t-invest",
            "account_id": account.account_id,
            "account_name": account.name,
            "created_at": now.isoformat(),
            "status": "submitted_to_broker",
            "submission_mode": "real",
            "would_submit": True,
            "submitted": True,
            "message": "Stop order was submitted to T-Invest.",
            "ticket": ticket.model_dump(mode="json"),
            "broker_response": payload,
        }

    async def get_last_price(
        self,
        *,
        instrument_id: str | None = None,
        figi: str | None = None,
    ) -> dict[str, Any]:
        token = self._require_token()
        if not instrument_id and not figi:
            raise HTTPException(
                status_code=422,
                detail="Pass instrument_id or figi.",
            )

        try:
            async with AsyncClient(token) as client:
                response = await client.market_data.get_last_prices(
                    instrument_id=[instrument_id] if instrument_id else None,
                    figi=[figi] if figi else None,
                )
        except (AioRequestError, InvestError) as error:
            raise self._broker_error(error) from error

        last_prices = response.last_prices
        if not last_prices:
            raise HTTPException(status_code=404, detail="Last price was not found.")

        last_price = last_prices[0]
        serialized_price = serialize_quotation(last_price.price)
        return {
            "figi": none_if_missing(last_price.figi),
            "instrument_uid": none_if_missing(last_price.instrument_uid),
            "instrument_id": instrument_id or none_if_missing(last_price.instrument_uid),
            "time": serialize_sdk_value(last_price.time),
            "last_price_type": serialize_sdk_value(last_price.last_price_type),
            "price": serialized_price,
            "price_value": None if serialized_price is None else serialized_price["value"],
        }

    async def stream_order_book(
        self,
        *,
        instrument_id: str | None = None,
        figi: str | None = None,
        depth: int = 20,
    ) -> AsyncIterator[dict[str, Any]]:
        token = self._require_token()
        if not instrument_id and not figi:
            raise HTTPException(
                status_code=422,
                detail="Pass instrument_id or figi.",
            )

        normalized_depth = max(1, min(depth, 50))
        instrument = OrderBookInstrument(
            figi=figi or "",
            instrument_id=instrument_id or "",
            depth=normalized_depth,
        )

        try:
            async with AsyncClient(token) as client:
                stream = client.create_market_data_stream()
                stream.order_book.subscribe([instrument])
                try:
                    async for response in stream:
                        order_book = getattr(response, "orderbook", None)
                        if is_missing_sdk_value(order_book):
                            continue
                        yield normalize_order_book(
                            order_book,
                            requested_instrument_id=instrument_id,
                        )
                finally:
                    stream.order_book.unsubscribe([instrument])
                    stream.stop()
        except (AioRequestError, InvestError) as error:
            raise self._broker_error(error) from error

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


def normalize_client_order_id(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return str(uuid.uuid4())
    try:
        return str(uuid.UUID(text))
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail="client_order_id must be empty or a UUID for T-Invest order submission.",
        ) from error


def quotation_from_float(value: float | None) -> Any | None:
    if value is None:
        return None
    return utils.decimal_to_quotation(Decimal(str(value)))


def order_direction(side: str) -> OrderDirection:
    return {
        "buy": OrderDirection.ORDER_DIRECTION_BUY,
        "sell": OrderDirection.ORDER_DIRECTION_SELL,
    }[side]


def stop_order_direction(side: str) -> StopOrderDirection:
    return {
        "buy": StopOrderDirection.STOP_ORDER_DIRECTION_BUY,
        "sell": StopOrderDirection.STOP_ORDER_DIRECTION_SELL,
    }[side]


def order_type(kind: str) -> OrderType:
    return {
        "limit": OrderType.ORDER_TYPE_LIMIT,
        "market": OrderType.ORDER_TYPE_MARKET,
    }[kind]


def stop_order_type(kind: str) -> StopOrderType:
    return {
        "stop_loss": StopOrderType.STOP_ORDER_TYPE_STOP_LOSS,
        "take_profit": StopOrderType.STOP_ORDER_TYPE_TAKE_PROFIT,
    }[kind]


def time_in_force(value: str) -> TimeInForceType:
    return {
        "day": TimeInForceType.TIME_IN_FORCE_DAY,
        "fill_and_kill": TimeInForceType.TIME_IN_FORCE_FILL_AND_KILL,
        "fill_or_kill": TimeInForceType.TIME_IN_FORCE_FILL_OR_KILL,
    }[value]


def price_type(value: str | None) -> PriceType:
    return {
        "currency": PriceType.PRICE_TYPE_CURRENCY,
        "point": PriceType.PRICE_TYPE_POINT,
    }.get(value or "currency", PriceType.PRICE_TYPE_CURRENCY)


def stop_order_expiration_type(
    expire_at: datetime | None,
) -> StopOrderExpirationType:
    if expire_at is None:
        return StopOrderExpirationType.STOP_ORDER_EXPIRATION_TYPE_GOOD_TILL_CANCEL
    return StopOrderExpirationType.STOP_ORDER_EXPIRATION_TYPE_GOOD_TILL_DATE


def exchange_order_type(limit_price: float | None) -> ExchangeOrderType:
    if limit_price is None:
        return ExchangeOrderType.EXCHANGE_ORDER_TYPE_MARKET
    return ExchangeOrderType.EXCHANGE_ORDER_TYPE_LIMIT


def normalize_expire_at(expire_at: datetime | None) -> datetime | None:
    if expire_at is None:
        return None
    if expire_at.tzinfo is None:
        return expire_at.replace(tzinfo=UTC)
    return expire_at.astimezone(UTC)


def normalize_order_book(
    order_book: Any,
    *,
    requested_instrument_id: str | None = None,
) -> dict[str, Any]:
    return {
        "type": "orderbook",
        "instrument_id": requested_instrument_id or none_if_missing(order_book.instrument_uid),
        "instrument_uid": none_if_missing(order_book.instrument_uid),
        "figi": none_if_missing(order_book.figi),
        "time": serialize_sdk_value(order_book.time),
        "depth": none_if_missing(order_book.depth),
        "is_consistent": none_if_missing(order_book.is_consistent),
        "order_book_type": serialize_sdk_value(order_book.order_book_type),
        "limit_up": quotation_value(order_book.limit_up),
        "limit_down": quotation_value(order_book.limit_down),
        "bids": normalize_order_book_rows(order_book.bids, reverse=True),
        "asks": normalize_order_book_rows(order_book.asks, reverse=False),
    }


def normalize_order_book_rows(rows: list[Any], *, reverse: bool) -> list[dict[str, Any]]:
    normalized = [
        {
            "price": quotation_value(row.price),
            "quantity": none_if_missing(row.quantity),
        }
        for row in rows
    ]
    return sorted(
        normalized,
        key=lambda row: float(row["price"] or 0),
        reverse=reverse,
    )


def quotation_value(value: Any) -> float | None:
    serialized = serialize_quotation(value)
    if serialized is None:
        return None
    return float(serialized["value"])


def none_if_missing(value: Any) -> Any:
    return None if is_missing_sdk_value(value) else value


def is_missing_sdk_value(value: Any) -> bool:
    return value is None or type(value) is object


__all__ = [
    "ExecutionService",
    "build_account_summary",
    "build_allocation",
    "exchange_order_type",
    "mask_account_id",
    "normalize_order_book",
    "normalize_client_order_id",
]
