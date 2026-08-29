from __future__ import annotations

import importlib
import inspect
import sys
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from t_tech.invest import (
    AsyncClient,
    ExchangeOrderType,
    GetOperationsByCursorRequest,
    OperationState,
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

from its.db.models.strategy import (
    TradingStrategyAccountAssignment,
    TradingStrategyProductionState,
)
from its.execution.config import ExecutionAccountConfig, load_execution_settings
from its.execution.pnl_report import build_pnl_report
from its.execution.schemas import (
    OrderTicket,
    StopOrderTicket,
    StrategyAssignmentRequest,
    StrategyExecutionRequest,
    StrategyRunRequest,
)
from its.execution.serialization import serialize_quotation, serialize_sdk_value
from its.execution.strategy_runner import (
    DATA_BACKEND_BASE_URL,
    StrategyRunSettings,
    auth_headers,
    build_strategy_run_preview,
    handle_data_response,
)


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

    async def get_pnl_report(
        self,
        account_id: str,
        *,
        from_date: date,
        to_date: date,
        strategy_name: str | None,
        session: Session,
        authorization: str | None,
    ) -> dict[str, Any]:
        account_ref = self._require_account(account_id)
        token = self._require_token()
        today = datetime.now(UTC).date()
        if from_date > to_date:
            raise HTTPException(
                status_code=422,
                detail="from_date must be before or equal to to_date.",
            )
        if to_date > today:
            raise HTTPException(
                status_code=422,
                detail="to_date cannot be in the future.",
            )
        if (to_date - from_date).days > 365 * 10:
            raise HTTPException(
                status_code=422,
                detail="PnL report period cannot exceed 10 years.",
            )

        assignments = list(
            session.scalars(
                select(TradingStrategyAccountAssignment)
                .where(TradingStrategyAccountAssignment.account_id == account_id)
                .order_by(TradingStrategyAccountAssignment.created_at)
            )
        )
        assigned_names = [row.strategy_name for row in assignments]
        if strategy_name and strategy_name not in assigned_names:
            raise HTTPException(
                status_code=404,
                detail="Strategy is not assigned to this execution account.",
            )

        try:
            async with AsyncClient(token) as client:
                accounts_response = await client.users.get_accounts()
                broker_account = next(
                    (
                        account
                        for account in accounts_response.accounts
                        if account.id == account_id
                    ),
                    None,
                )
                if broker_account is None:
                    raise HTTPException(
                        status_code=404,
                        detail="Configured account was not returned by T-Invest.",
                    )
                operations = await self._get_all_operations(
                    client,
                    account_id=account_id,
                    to=datetime.combine(to_date, time.max, UTC),
                )
                current_portfolio = None
                if to_date == today:
                    current_portfolio = serialize_sdk_value(
                        await client.operations.get_portfolio(account_id=account_id)
                    )
        except HTTPException:
            raise
        except (AioRequestError, InvestError) as error:
            raise self._broker_error(error) from error

        portfolio_positions = (current_portfolio or {}).get("positions") or []
        figis = sorted(
            {
                str(figi)
                for figi in [
                    *(row.get("figi") for row in operations),
                    *(row.get("figi") for row in portfolio_positions),
                ]
                if figi
            }
        )
        prices = await self._get_pnl_prices(
            figis,
            from_date=from_date - timedelta(days=14),
            to_date=to_date,
            authorization=authorization,
        )
        account_item = self._build_account_item(
            ExecutionAccountConfig(account_ref.account_id, account_ref.name),
            broker_account,
        )
        current_portfolio_value = _extract_value(
            (current_portfolio or {}).get("total_amount_portfolio")
        )
        report = build_pnl_report(
            account_id=account_id,
            account_name=str(
                account_item.get("name") or account_ref.name or account_id
            ),
            from_date=from_date,
            to_date=to_date,
            operations=operations,
            prices=prices,
            strategy_name=strategy_name,
            assigned_strategies=assigned_names,
            current_portfolio_value=current_portfolio_value,
        )
        report["generated_at"] = datetime.now(UTC).isoformat()
        return report

    async def _get_all_operations(
        self,
        client: Any,
        *,
        account_id: str,
        to: datetime,
    ) -> list[dict[str, Any]]:
        cursor: str | None = None
        result: list[dict[str, Any]] = []
        for _ in range(100):
            response = await client.operations.get_operations_by_cursor(
                GetOperationsByCursorRequest(
                    account_id=account_id,
                    to=to,
                    cursor=cursor,
                    limit=1000,
                    state=OperationState.OPERATION_STATE_EXECUTED,
                    without_commissions=False,
                    without_trades=False,
                    without_overnights=False,
                )
            )
            payload = serialize_sdk_value(response) or {}
            result.extend(payload.get("items") or [])
            if not payload.get("has_next"):
                return result
            next_cursor = str(payload.get("next_cursor") or "").strip()
            if not next_cursor or next_cursor == cursor:
                raise HTTPException(
                    status_code=502,
                    detail="T-Invest returned an invalid operations cursor.",
                )
            cursor = next_cursor
        raise HTTPException(
            status_code=502,
            detail="T-Invest operations history exceeded the pagination safety limit.",
        )

    async def _get_pnl_prices(
        self,
        figis: list[str],
        *,
        from_date: date,
        to_date: date,
        authorization: str | None,
    ) -> list[dict[str, Any]]:
        if not figis:
            return []
        result: list[dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=None) as client:
            for index in range(0, len(figis), 50):
                params: list[tuple[str, str]] = [
                    ("figis", figi) for figi in figis[index : index + 50]
                ]
                params.extend(
                    [
                        ("instrument_type", "all"),
                        ("class_code", ""),
                        ("start_date", from_date.isoformat()),
                        ("end_date", to_date.isoformat()),
                        ("interval", "CANDLE_INTERVAL_DAY"),
                        ("is_complete", "false"),
                    ]
                )
                response = await client.get(
                    f"{DATA_BACKEND_BASE_URL}/prices",
                    params=params,
                    headers=auth_headers(authorization),
                )
                payload = handle_data_response(response)
                result.extend(payload.get("items") or [])
        return result

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
                    price=(
                        quotation_from_float(ticket.price)
                        if ticket.order_type == "limit"
                        else None
                    ),
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
        execution_status = payload.get("execution_report_status")
        rejected = "REJECT" in str(execution_status or "").upper()
        default_message = (
            "T-Invest rejected the order."
            if rejected
            else "Order was submitted to T-Invest."
        )
        return {
            "id": broker_order_id,
            "broker_order_id": broker_order_id,
            "broker": "t-invest",
            "account_id": account.account_id,
            "account_name": account.name,
            "created_at": now.isoformat(),
            "status": execution_status or "submitted_to_broker",
            "submission_mode": "real",
            "would_submit": True,
            "submitted": not rejected,
            "message": payload.get("message") or default_message,
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
            "instrument_id": instrument_id
            or none_if_missing(last_price.instrument_uid),
            "time": serialize_sdk_value(last_price.time),
            "last_price_type": serialize_sdk_value(last_price.last_price_type),
            "price": serialized_price,
            "price_value": (
                None if serialized_price is None else serialized_price["value"]
            ),
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

    def list_strategy_assignments(
        self,
        account_id: str,
        session: Session,
    ) -> dict[str, Any]:
        account = self._require_account(account_id)
        registered = registered_trading_strategy_items()
        states = load_production_states(session)
        assignments = (
            session.execute(
                select(TradingStrategyAccountAssignment)
                .where(
                    TradingStrategyAccountAssignment.account_id == account.account_id
                )
                .order_by(TradingStrategyAccountAssignment.created_at.desc())
            )
            .scalars()
            .all()
        )
        assigned_items = [
            serialize_strategy_assignment(row, registered, states)
            for row in assignments
        ]
        available = [
            {
                **item,
                "production_state": serialize_strategy_production_state(
                    states.get(item["name"]), strategy_name=item["name"]
                ),
                "is_assigned": any(
                    assignment.strategy_name == item["name"]
                    for assignment in assignments
                ),
            }
            for item in registered.values()
            if (states.get(item["name"]) and states[item["name"]].is_prod_ready)
        ]
        available.sort(key=lambda item: item["name"])
        return {
            "account_id": account.account_id,
            "items": assigned_items,
            "available": available,
            "total": len(assigned_items),
        }

    def assign_strategy(
        self,
        account_id: str,
        strategy_name: str,
        payload: StrategyAssignmentRequest,
        session: Session,
        assigned_by_user_id: Any,
    ) -> dict[str, Any]:
        account = self._require_account(account_id)
        registered = registered_trading_strategy_items()
        if strategy_name not in registered:
            raise HTTPException(
                status_code=404, detail="Trading strategy is not registered."
            )

        states = load_production_states(session)
        state = states.get(strategy_name)
        if state is None or not state.is_prod_ready:
            raise HTTPException(
                status_code=422,
                detail="Trading strategy is not marked as production-ready.",
            )

        row = (
            session.execute(
                select(TradingStrategyAccountAssignment).where(
                    TradingStrategyAccountAssignment.account_id == account.account_id,
                    TradingStrategyAccountAssignment.strategy_name == strategy_name,
                )
            )
            .scalars()
            .one_or_none()
        )
        if row is None:
            row = TradingStrategyAccountAssignment(
                account_id=account.account_id,
                strategy_name=strategy_name,
            )
            session.add(row)

        row.comment = payload.comment.strip() if payload.comment else None
        row.assigned_by_user_id = assigned_by_user_id
        try:
            session.commit()
        except IntegrityError as error:
            session.rollback()
            raise HTTPException(
                status_code=409,
                detail="Trading strategy is already assigned to this account.",
            ) from error
        session.refresh(row)
        return {
            "item": serialize_strategy_assignment(row, registered, states),
        }

    def unassign_strategy(
        self,
        account_id: str,
        strategy_name: str,
        session: Session,
    ) -> dict[str, Any]:
        account = self._require_account(account_id)
        row = (
            session.execute(
                select(TradingStrategyAccountAssignment).where(
                    TradingStrategyAccountAssignment.account_id == account.account_id,
                    TradingStrategyAccountAssignment.strategy_name == strategy_name,
                )
            )
            .scalars()
            .one_or_none()
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Assignment was not found.")
        session.delete(row)
        session.commit()
        return {"status": "deleted"}

    async def run_assigned_strategy(
        self,
        account_id: str,
        strategy_name: str,
        request: StrategyRunRequest,
        session: Session,
        authorization: str | None,
    ) -> dict[str, Any]:
        account = self._require_account(account_id)
        assignment = (
            session.execute(
                select(TradingStrategyAccountAssignment).where(
                    TradingStrategyAccountAssignment.account_id == account.account_id,
                    TradingStrategyAccountAssignment.strategy_name == strategy_name,
                )
            )
            .scalars()
            .one_or_none()
        )
        if assignment is None:
            raise HTTPException(
                status_code=404,
                detail="Assign this strategy to the account before running it.",
            )

        production_state = (
            session.execute(
                select(TradingStrategyProductionState).where(
                    TradingStrategyProductionState.strategy_name == strategy_name
                )
            )
            .scalars()
            .one_or_none()
        )
        if production_state is None or not production_state.is_prod_ready:
            raise HTTPException(
                status_code=422,
                detail="The assigned strategy is no longer marked as production-ready.",
            )

        overview = await self.get_account_overview(
            account.account_id, operations_days=1
        )
        preview = await build_strategy_run_preview(
            strategy_name=strategy_name,
            account_id=account.account_id,
            account_overview=overview,
            settings=StrategyRunSettings(
                start_date=request.start_date,
                end_date=request.end_date,
                interval=request.interval,
                class_code=request.class_code,
                order_type=request.order_type,
                limit_offset_pct=request.limit_offset_pct,
                min_order_value=request.min_order_value,
                cash_buffer_pct=request.cash_buffer_pct,
            ),
            authorization=authorization,
        )
        if self.settings.order_submission_mode == "real" and preview.get("orders"):
            try:
                availability = await self.get_market_order_availability(
                    preview["orders"]
                )
            except HTTPException as error:
                preview["execution"]["ready"] = False
                preview["execution"]["blocking_reasons"].append(
                    broker_error_message(error.detail)
                )
            else:
                preview["execution"]["market_order_availability"] = availability
                unavailable = [row for row in availability if not row["available"]]
                if unavailable:
                    tickers = ", ".join(row["ticker"] for row in unavailable)
                    preview["execution"]["ready"] = False
                    preview["execution"]["blocking_reasons"].append(
                        "T-Invest сейчас не принимает рыночные заявки для: "
                        f"{tickers}. Дождитесь доступности market-заявок или "
                        "используйте отдельный подтверждаемый режим лимитных заявок."
                    )
        return preview

    async def get_market_order_availability(
        self,
        orders: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        token = self._require_token()
        instrument_ids = list(
            dict.fromkeys(
                str(row.get("instrument_id") or "")
                for row in orders
                if row.get("instrument_id")
            )
        )
        if not instrument_ids:
            return []

        try:
            async with AsyncClient(token) as client:
                response = await client.market_data.get_trading_statuses(
                    instrument_ids=instrument_ids
                )
        except (AioRequestError, InvestError) as error:
            raise self._broker_error(error) from error

        payload = serialize_sdk_value(response) or {}
        statuses = payload.get("trading_statuses") or []
        status_by_id: dict[str, dict[str, Any]] = {}
        for status in statuses:
            for key in ("instrument_uid", "figi"):
                value = status.get(key)
                if value:
                    status_by_id[str(value)] = status

        result: list[dict[str, Any]] = []
        for order in orders:
            instrument_id = str(order.get("instrument_id") or "")
            status = status_by_id.get(instrument_id)
            result.append(
                {
                    "ticker": str(order.get("ticker") or instrument_id),
                    "instrument_id": instrument_id,
                    "available": bool(
                        status
                        and status.get("api_trade_available_flag") is True
                        and status.get("market_order_available_flag") is True
                    ),
                    "api_trade_available_flag": (
                        status.get("api_trade_available_flag") if status else None
                    ),
                    "market_order_available_flag": (
                        status.get("market_order_available_flag") if status else None
                    ),
                    "limit_order_available_flag": (
                        status.get("limit_order_available_flag") if status else None
                    ),
                    "bestprice_order_available_flag": (
                        status.get("bestprice_order_available_flag") if status else None
                    ),
                    "only_best_price": (
                        status.get("only_best_price") if status else None
                    ),
                    "trading_status": (
                        status.get("trading_status") if status else None
                    ),
                }
            )
        return result

    async def execute_assigned_strategy(
        self,
        account_id: str,
        strategy_name: str,
        request: StrategyExecutionRequest,
        session: Session,
        authorization: str | None,
        requested_by_user_id: Any,
    ) -> dict[str, Any]:
        preview = await self.run_assigned_strategy(
            account_id,
            strategy_name,
            request,
            session,
            authorization,
        )
        if preview["plan_id"] != request.plan_id:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": (
                        "The broker portfolio or strategy plan changed. "
                        "Review the refreshed preview before executing it."
                    ),
                    "expected_plan_id": request.plan_id,
                    "current_plan_id": preview["plan_id"],
                },
            )

        execution = preview.get("execution") or {}
        if not execution.get("ready"):
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "The strategy plan is not safe to execute.",
                    "blocking_reasons": execution.get("blocking_reasons") or [],
                },
            )

        return await self.execute_strategy_orders(
            account_id=account_id,
            strategy_name=strategy_name,
            plan=preview,
            requested_by_user_id=requested_by_user_id,
        )

    async def execute_strategy_orders(
        self,
        *,
        account_id: str,
        strategy_name: str,
        plan: dict[str, Any],
        requested_by_user_id: Any,
    ) -> dict[str, Any]:
        plan_id = str(plan["plan_id"])
        orders = list(plan.get("orders") or [])
        ordered_rows = [row for row in orders if row["side"] == "sell"] + [
            row for row in orders if row["side"] == "buy"
        ]
        results: list[dict[str, Any]] = []
        sell_failed = False

        for index, row in enumerate(ordered_rows):
            if row["side"] == "buy" and sell_failed:
                results.append(
                    strategy_order_result(
                        row,
                        status="skipped",
                        error="Buy phase was skipped because at least one sell order failed.",
                    )
                )
                continue

            client_order_id = str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    (
                        f"its:strategy-execution:{plan_id}:{index}:"
                        f"{row['ticker']}:{row['side']}"
                    ),
                )
            )
            ticket = OrderTicket(
                instrument_id=str(row["instrument_id"]),
                figi=row.get("figi"),
                side=row["side"],
                order_type="market",
                quantity=int(row["quantity_lots"]),
                client_order_id=client_order_id,
                comment=(
                    f"Strategy {strategy_name}; plan {plan_id[:12]}; "
                    f"requested_by={requested_by_user_id}"
                ),
            )
            try:
                response = await self.submit_order(account_id, ticket)
            except HTTPException as error:
                if row["side"] == "sell":
                    sell_failed = True
                results.append(
                    strategy_order_result(
                        row,
                        status="failed",
                        client_order_id=client_order_id,
                        error=error.detail,
                    )
                )
                continue

            if response.get("submission_mode") == "stub":
                status = "simulated"
            elif response.get("submitted"):
                status = "submitted"
            else:
                status = "failed"
                if row["side"] == "sell":
                    sell_failed = True
            results.append(
                strategy_order_result(
                    row,
                    status=status,
                    client_order_id=client_order_id,
                    response=response,
                    error=(
                        None
                        if status != "failed"
                        else response.get("message") or "Broker rejected the order."
                    ),
                )
            )

        failed = len([row for row in results if row["status"] == "failed"])
        skipped = len([row for row in results if row["status"] == "skipped"])
        submitted = len([row for row in results if row["status"] == "submitted"])
        simulated = len([row for row in results if row["status"] == "simulated"])
        if failed or skipped:
            status = "partial"
        elif simulated:
            status = "simulated"
        else:
            status = "submitted"

        return {
            "execution_id": plan_id,
            "plan_id": plan_id,
            "account_id": account_id,
            "strategy_name": strategy_name,
            "requested_by_user_id": str(requested_by_user_id),
            "executed_at": datetime.now(UTC).isoformat(),
            "submission_mode": self.settings.order_submission_mode,
            "status": status,
            "sell_first": True,
            "stop_orders_submitted": False,
            "summary": {
                "orders": len(results),
                "submitted": submitted,
                "simulated": simulated,
                "failed": failed,
                "skipped": skipped,
            },
            "results": results,
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
                return AccountReference(
                    account_id=account.account_id, name=account.name
                )
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
        payload["name"] = (
            config.name or payload.get("name") or mask_account_id(account.id)
        )
        payload["is_configured"] = True
        payload["is_available"] = True
        return payload

    @staticmethod
    def _broker_error(error: Exception) -> HTTPException:
        metadata = getattr(error, "metadata", None)
        broker_code = str(getattr(error, "details", "") or "")
        broker_message = str(getattr(metadata, "message", "") or "")
        tracking_id = str(getattr(metadata, "tracking_id", "") or "")
        if broker_code == "30083":
            message = (
                "T-Invest отклонил тип заявки (код 30083): выбранный тип "
                "недоступен для инструмента или текущего режима торгов."
            )
        elif broker_message:
            message = f"T-Invest: {broker_message}"
        else:
            message = f"T-Invest request failed: {error}"
        return HTTPException(
            status_code=502,
            detail={
                "message": message,
                "broker_code": broker_code or None,
                "broker_message": broker_message or None,
                "tracking_id": tracking_id or None,
            },
        )


def registered_trading_strategy_items() -> dict[str, dict[str, Any]]:
    module_name = "its.strategies_model.model"
    for name in sorted(sys.modules, reverse=True):
        if name == module_name or name.startswith(f"{module_name}."):
            del sys.modules[name]
    module = importlib.import_module(module_name)
    result: dict[str, dict[str, Any]] = {}
    for strategy_name in getattr(module, "__all__", []):
        obj = getattr(module, strategy_name, None)
        if obj is None:
            continue
        result[strategy_name] = {
            "name": strategy_name,
            "module": getattr(obj, "__module__", module_name),
            "description": compact_doc(inspect.getdoc(obj) or ""),
            "source_path": inspect.getsourcefile(obj) or "",
        }
    return result


def load_production_states(
    session: Session,
) -> dict[str, TradingStrategyProductionState]:
    return {
        row.strategy_name: row
        for row in session.execute(select(TradingStrategyProductionState)).scalars()
    }


def serialize_strategy_assignment(
    assignment: TradingStrategyAccountAssignment,
    registered: dict[str, dict[str, Any]],
    states: dict[str, TradingStrategyProductionState],
) -> dict[str, Any]:
    strategy = registered.get(assignment.strategy_name, {})
    return {
        "id": str(assignment.id),
        "account_id": assignment.account_id,
        "strategy_name": assignment.strategy_name,
        "comment": assignment.comment,
        "assigned_by_user_id": (
            str(assignment.assigned_by_user_id)
            if assignment.assigned_by_user_id
            else None
        ),
        "created_at": (
            assignment.created_at.isoformat() if assignment.created_at else None
        ),
        "updated_at": (
            assignment.updated_at.isoformat() if assignment.updated_at else None
        ),
        "strategy": {
            **strategy,
            "production_state": serialize_strategy_production_state(
                states.get(assignment.strategy_name),
                strategy_name=assignment.strategy_name,
            ),
        },
    }


def serialize_strategy_production_state(
    state: TradingStrategyProductionState | None,
    strategy_name: str | None = None,
) -> dict[str, Any]:
    if state is None:
        return {
            "strategy_name": strategy_name,
            "is_prod_ready": False,
            "comment": None,
            "updated_by_user_id": None,
            "updated_at": None,
        }
    return {
        "strategy_name": state.strategy_name,
        "is_prod_ready": state.is_prod_ready,
        "comment": state.comment,
        "updated_by_user_id": (
            str(state.updated_by_user_id) if state.updated_by_user_id else None
        ),
        "updated_at": state.updated_at.isoformat() if state.updated_at else None,
    }


def compact_doc(doc: str, limit: int = 500) -> str:
    paragraphs = [part.strip() for part in doc.split("\n\n") if part.strip()]
    text = paragraphs[0] if paragraphs else doc.strip()
    text = " ".join(line.strip() for line in text.splitlines() if line.strip())
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1].rstrip()}..."


def broker_error_message(detail: Any) -> str:
    if isinstance(detail, str):
        return detail
    if isinstance(detail, dict) and isinstance(detail.get("message"), str):
        return detail["message"]
    return "Не удалось проверить доступность рыночных заявок в T-Invest."


def strategy_order_result(
    row: dict[str, Any],
    *,
    status: str,
    client_order_id: str | None = None,
    response: dict[str, Any] | None = None,
    error: Any = None,
) -> dict[str, Any]:
    return {
        "ticker": row.get("ticker"),
        "figi": row.get("figi"),
        "instrument_id": row.get("instrument_id"),
        "side": row.get("side"),
        "quantity_lots": row.get("quantity_lots"),
        "estimated_amount": row.get("estimated_amount"),
        "status": status,
        "client_order_id": client_order_id,
        "broker_order_id": (response or {}).get("broker_order_id"),
        "response": response,
        "error": error,
    }


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
        "instrument_id": requested_instrument_id
        or none_if_missing(order_book.instrument_uid),
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


def normalize_order_book_rows(
    rows: list[Any], *, reverse: bool
) -> list[dict[str, Any]]:
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
    "normalize_client_order_id",
    "normalize_order_book",
]
