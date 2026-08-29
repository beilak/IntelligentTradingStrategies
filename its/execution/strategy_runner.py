from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import numpy as np
import pandas as pd
from fastapi import HTTPException

from its.strategies.testing.backtest.core import (
    build_close_prices,
    build_price_matrix,
    load_registered_trading_strategy,
)
from its.strategies.testing.backtest.vectorbt_backtest import _build_order_plan

DATA_BACKEND_BASE_URL = os.getenv(
    "DATA_BACKEND_BASE_URL",
    "http://data-backend:8000/api/v1",
).rstrip("/")
MARKET_TIME_ZONE = ZoneInfo("Europe/Moscow")


@dataclass(frozen=True)
class StrategyRunSettings:
    start_date: date | None
    end_date: date | None
    interval: str
    class_code: str
    order_type: str
    limit_offset_pct: float
    min_order_value: float
    cash_buffer_pct: float


async def build_strategy_run_preview(
    *,
    strategy_name: str,
    account_id: str,
    account_overview: dict[str, Any],
    settings: StrategyRunSettings,
    authorization: str | None,
) -> dict[str, Any]:
    end_date = settings.end_date or datetime.now(MARKET_TIME_ZONE).date()
    start_date = settings.start_date or end_date - timedelta(days=365)
    if start_date >= end_date:
        raise HTTPException(
            status_code=422, detail="start_date must be before end_date."
        )

    stocks = await fetch_stocks(settings.class_code, authorization=authorization)
    figis = [str(item.get("figi")) for item in stocks if item.get("figi")]
    if not figis:
        raise HTTPException(status_code=404, detail="No assets found for strategy run.")

    prices = await fetch_prices(
        figis,
        start_date=start_date,
        end_date=end_date,
        interval=settings.interval,
        class_code=settings.class_code,
        authorization=authorization,
    )
    if prices.empty:
        raise HTTPException(status_code=404, detail="No prices found for strategy run.")

    close = build_close_prices(prices)
    if len(close.index) < 2:
        raise HTTPException(
            status_code=422,
            detail="At least two price rows are required to run a strategy.",
        )

    strategy_cls = load_registered_trading_strategy(strategy_name)
    trading_strategy = strategy_cls(
        prices,
        pd.DataFrame(stocks),
        _dividends_info=pd.DataFrame(),
    ).build()
    _require_live_execution_support(trading_strategy)
    run_time = close.index[-1]
    high = build_price_matrix(prices, "high", close)
    low = build_price_matrix(prices, "low", close)
    weights, _, _ = _build_order_plan(
        trading_strategy,
        close,
        pd.Index([run_time]),
        trading_start_date=run_time,
        high=high,
        low=low,
    )
    target_weights = weights.loc[run_time].fillna(0.0)

    return build_preview_payload(
        strategy=trading_strategy,
        account_id=account_id,
        account_overview=account_overview,
        stocks=stocks,
        close=close,
        target_weights=target_weights,
        run_time=run_time,
        settings=StrategyRunSettings(
            start_date=start_date,
            end_date=end_date,
            interval=settings.interval,
            class_code=settings.class_code,
            order_type=settings.order_type,
            limit_offset_pct=settings.limit_offset_pct,
            min_order_value=settings.min_order_value,
            cash_buffer_pct=settings.cash_buffer_pct,
        ),
    )


async def fetch_stocks(
    class_code: str,
    *,
    authorization: str | None,
) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=None) as client:
        response = await client.get(
            f"{DATA_BACKEND_BASE_URL}/stocks",
            params={"class_code": class_code, "limit": 500},
            headers=auth_headers(authorization),
        )
    payload = handle_data_response(response)
    return payload.get("items", [])


async def fetch_prices(
    figis: list[str],
    *,
    start_date: date,
    end_date: date,
    interval: str,
    class_code: str,
    authorization: str | None,
) -> pd.DataFrame:
    params: list[tuple[str, str]] = [("figis", figi) for figi in figis]
    params.extend(
        [
            ("class_code", class_code),
            ("instrument_type", "stocks"),
            ("start_date", start_date.isoformat()),
            ("end_date", end_date.isoformat()),
            ("interval", interval),
            ("is_complete", "true"),
        ]
    )
    async with httpx.AsyncClient(timeout=None) as client:
        response = await client.get(
            f"{DATA_BACKEND_BASE_URL}/prices",
            params=params,
            headers=auth_headers(authorization),
        )
    payload = handle_data_response(response)
    return pd.DataFrame(payload.get("items", []))


def handle_data_response(response: httpx.Response) -> dict[str, Any]:
    if response.is_success:
        return response.json()
    try:
        detail = response.json().get("detail", response.text)
    except ValueError:
        detail = response.text
    raise HTTPException(
        status_code=502,
        detail=f"Data backend request failed: {detail}",
    )


def auth_headers(authorization: str | None) -> dict[str, str]:
    return {"Authorization": authorization} if authorization else {}


def build_preview_payload(
    *,
    strategy: Any,
    account_id: str,
    account_overview: dict[str, Any],
    stocks: list[dict[str, Any]],
    close: pd.DataFrame,
    target_weights: pd.Series,
    run_time: pd.Timestamp,
    settings: StrategyRunSettings,
) -> dict[str, Any]:
    _require_live_execution_support(strategy)
    stock_by_ticker = {
        str(item.get("ticker")): item for item in stocks if item.get("ticker")
    }
    stock_by_figi = {str(item.get("figi")): item for item in stocks if item.get("figi")}
    latest_prices = close.loc[run_time].dropna()
    current_positions = build_current_position_map(account_overview, stock_by_figi)
    portfolio_value = resolve_portfolio_value(account_overview, current_positions)
    if portfolio_value <= 0:
        raise HTTPException(
            status_code=422,
            detail="Portfolio value is missing or zero; cannot calculate order plan.",
        )

    model_target_positions = len(
        [value for value in target_weights if (safe_float(value) or 0.0) > 1e-12]
    )
    target_rows: list[dict[str, Any]] = []
    unpriced_positions: list[str] = []

    tickers = sorted(
        set(latest_prices.index.astype(str))
        | set(target_weights.index.astype(str))
        | set(current_positions)
    )
    for ticker in tickers:
        stock = stock_by_ticker.get(ticker, {})
        price = safe_float(latest_prices.get(ticker))
        if not is_positive(price):
            current_lots_without_price = (
                safe_float(current_positions.get(ticker, {}).get("lots")) or 0.0
            )
            target_weight_without_price = safe_float(target_weights.get(ticker)) or 0.0
            if (
                abs(current_lots_without_price) > 1e-12
                or abs(target_weight_without_price) > 1e-12
            ):
                unpriced_positions.append(ticker)
            continue

        lot = int(safe_float(stock.get("lot")) or 1)
        lot = max(lot, 1)
        current = current_positions.get(ticker, {})
        current_lots = safe_float(current.get("lots")) or 0.0
        blocked_lots = max(safe_float(current.get("blocked_lots")) or 0.0, 0.0)
        available_lots = max(current_lots - blocked_lots, 0.0)
        current_quantity = safe_float(current.get("quantity")) or current_lots * lot
        current_value = current_quantity * price
        current_weight = current_value / portfolio_value if portfolio_value else 0.0
        target_weight = safe_float(target_weights.get(ticker)) or 0.0
        if not np.isfinite(target_weight) or abs(target_weight) < 1e-12:
            target_weight = 0.0
        target_value = max(target_weight, 0.0) * portfolio_value
        one_lot_value = price * lot
        model_target_lots = (
            int(target_value // one_lot_value) if one_lot_value > 0 else 0
        )
        delta_lots = model_target_lots - round(current_lots)
        delta_value = delta_lots * lot * price

        row = {
            "ticker": ticker,
            "figi": stock.get("figi") or current.get("figi"),
            "instrument_id": stock.get("uid")
            or stock.get("instrument_uid")
            or stock.get("figi")
            or current.get("instrument_uid"),
            "name": stock.get("name") or current.get("name") or ticker,
            "sector": stock.get("sector"),
            "currency": stock.get("currency") or "rub",
            "lot": lot,
            "api_trade_available_flag": stock.get("api_trade_available_flag"),
            "buy_available_flag": stock.get("buy_available_flag"),
            "sell_available_flag": stock.get("sell_available_flag"),
            "market_order_available_flag": stock.get("market_order_available_flag"),
            "limit_order_available_flag": stock.get("limit_order_available_flag"),
            "bestprice_order_available_flag": stock.get(
                "bestprice_order_available_flag"
            ),
            "last_price": price,
            "current_lots": current_lots,
            "blocked_lots": blocked_lots,
            "available_lots": available_lots,
            "current_quantity": current_quantity,
            "current_value": current_value,
            "current_weight": current_weight,
            "target_weight": target_weight,
            "target_value": target_value,
            "one_lot_value": one_lot_value,
            "model_target_lots": model_target_lots,
            "target_lots": model_target_lots,
            "planned_weight": model_target_lots * one_lot_value / portfolio_value,
            "target_status": "planned",
            "delta_lots": delta_lots,
            "delta_value": delta_value,
        }

        if target_weight > 1e-12 or abs(current_lots) > 1e-12 or abs(delta_lots) > 0:
            target_rows.append(row)

    cash_plan = apply_cash_and_lot_constraints(
        target_rows,
        account_overview=account_overview,
        portfolio_value=portfolio_value,
        currency=primary_currency(account_overview),
        min_order_value=settings.min_order_value,
        cash_buffer_pct=settings.cash_buffer_pct,
    )
    orders = [
        build_order_row(row, settings)
        for row in target_rows
        if abs(int(row["delta_lots"])) > 0
    ]
    stop_orders = [
        stop_row
        for row in target_rows
        if int(row["target_lots"]) > 0
        for stop_row in build_stop_rows(row, strategy)
    ]

    orders = sorted(
        orders, key=lambda item: abs(item["estimated_amount"]), reverse=True
    )
    stop_orders = sorted(stop_orders, key=lambda item: (item["ticker"], item["kind"]))
    target_rows = sorted(
        target_rows,
        key=lambda item: abs(item["target_weight"] - item["current_weight"]),
        reverse=True,
    )

    gross_buy = sum(
        item["estimated_amount"] for item in orders if item["side"] == "buy"
    )
    gross_sell = sum(
        item["estimated_amount"] for item in orders if item["side"] == "sell"
    )
    blocking_reasons = build_execution_blocking_reasons(
        account_overview=account_overview,
        settings=settings,
        target_rows=target_rows,
        orders=orders,
        unpriced_positions=unpriced_positions,
    )
    payload = {
        "account_id": account_id,
        "strategy_name": getattr(strategy, "name", None),
        "strategy_description": getattr(strategy, "description", ""),
        "generated_at": datetime.now(MARKET_TIME_ZONE).isoformat(),
        "run_time": pd.Timestamp(run_time).isoformat(),
        "settings": {
            "start_date": (
                settings.start_date.isoformat() if settings.start_date else None
            ),
            "end_date": settings.end_date.isoformat() if settings.end_date else None,
            "interval": settings.interval,
            "class_code": settings.class_code,
            "order_type": settings.order_type,
            "limit_offset_pct": settings.limit_offset_pct,
            "min_order_value": settings.min_order_value,
            "cash_buffer_pct": settings.cash_buffer_pct,
        },
        "portfolio": {
            "value": portfolio_value,
            "currency": primary_currency(account_overview),
        },
        "summary": {
            "target_positions": cash_plan["planned_target_positions"],
            "model_target_positions": model_target_positions,
            "planned_target_positions": cash_plan["planned_target_positions"],
            "below_one_lot_target_positions": cash_plan[
                "below_one_lot_target_positions"
            ],
            "cash_limited_target_positions": cash_plan["cash_limited_target_positions"],
            "below_min_order_positions": cash_plan["below_min_order_positions"],
            "orders": len(orders),
            "buy_orders": len([item for item in orders if item["side"] == "buy"]),
            "sell_orders": len([item for item in orders if item["side"] == "sell"]),
            "stop_orders": len(stop_orders),
            "gross_buy": gross_buy,
            "gross_sell": gross_sell,
            "net_cash_need": gross_buy - gross_sell,
            "estimated_cash_change": gross_sell - gross_buy,
            "available_cash": cash_plan["available_cash"],
            "buying_power_after_sells": cash_plan["buying_power_after_sells"],
            "estimated_cash_after_orders": cash_plan["estimated_cash_after_orders"],
            "conservative_cash_after_orders": cash_plan[
                "conservative_cash_after_orders"
            ],
            "minimum_one_lot_cost": cash_plan["minimum_one_lot_cost"],
            "lot_rounding_unallocated_value": cash_plan[
                "lot_rounding_unallocated_value"
            ],
        },
        "target_weights": target_rows,
        "orders": orders,
        "stop_orders": stop_orders,
    }
    payload["plan_id"] = build_plan_id(payload)
    payload["execution"] = {
        "ready": bool(orders) and not blocking_reasons,
        "blocking_reasons": blocking_reasons,
        "warnings": build_execution_warnings(cash_plan),
        "order_type": "market",
        "sell_first": True,
        "stop_orders_included": False,
    }
    return payload


def _require_live_execution_support(strategy: Any) -> None:
    if getattr(strategy, "supports_live_execution", True):
        return
    raise HTTPException(
        status_code=422,
        detail=(
            "This strategy requires persisted position and trailing-stop state; "
            "live execution is not supported yet. Use the backtest workflow."
        ),
    )


def apply_cash_and_lot_constraints(
    target_rows: list[dict[str, Any]],
    *,
    account_overview: dict[str, Any],
    portfolio_value: float,
    currency: str,
    min_order_value: float,
    cash_buffer_pct: float,
) -> dict[str, Any]:
    for row in target_rows:
        current_lots = round(float(row["current_lots"]))
        model_target_lots = int(row["model_target_lots"])
        model_delta_lots = model_target_lots - current_lots
        row["model_delta_lots"] = model_delta_lots
        row["constraint"] = None
        row["target_lots"] = model_target_lots

        if row["target_weight"] > 1e-12 and model_target_lots == 0:
            row["constraint"] = "below_one_lot"

        if (
            model_delta_lots != 0
            and abs(model_delta_lots * row["one_lot_value"]) < min_order_value
        ):
            row["target_lots"] = current_lots
            row["constraint"] = "below_min_order"

    gross_sell = sum(
        max(round(row["current_lots"]) - int(row["target_lots"]), 0)
        * row["one_lot_value"]
        for row in target_rows
    )
    available_cash = resolve_available_cash(
        account_overview,
        currency=currency,
        portfolio_value=portfolio_value,
        target_rows=target_rows,
    )
    buying_power_after_sells = max(
        available_cash + gross_sell * (1 - cash_buffer_pct),
        0.0,
    )
    remaining_buying_power = buying_power_after_sells

    buy_rows = sorted(
        (
            row
            for row in target_rows
            if int(row["target_lots"]) > round(row["current_lots"])
        ),
        key=lambda row: (
            -(row["target_weight"] - row["current_weight"]),
            -row["target_weight"],
            row["ticker"],
        ),
    )
    for row in buy_rows:
        current_lots = round(row["current_lots"])
        requested_lots = int(row["target_lots"]) - current_lots
        buffered_lot_cost = row["one_lot_value"] * (1 + cash_buffer_pct)
        affordable_lots = (
            int((remaining_buying_power + 1e-9) // buffered_lot_cost)
            if buffered_lot_cost > 0
            else 0
        )
        planned_lots = min(requested_lots, max(affordable_lots, 0))
        row["target_lots"] = current_lots + planned_lots
        remaining_buying_power = max(
            remaining_buying_power - planned_lots * buffered_lot_cost,
            0.0,
        )
        if planned_lots < requested_lots:
            row["constraint"] = "cash_limited"

    for row in target_rows:
        current_lots = round(row["current_lots"])
        target_lots = int(row["target_lots"])
        delta_lots = target_lots - current_lots
        row["delta_lots"] = delta_lots
        row["delta_value"] = delta_lots * row["one_lot_value"]
        row["planned_value"] = target_lots * row["one_lot_value"]
        row["planned_weight"] = row["planned_value"] / portfolio_value
        if delta_lots > 0:
            row["target_status"] = "buy"
        elif delta_lots < 0:
            row["target_status"] = "sell"
        elif target_lots > 0:
            row["target_status"] = "keep"
        else:
            row["target_status"] = "no_action"

    gross_buy = sum(
        max(int(row["delta_lots"]), 0) * row["one_lot_value"] for row in target_rows
    )
    gross_sell = sum(
        max(-int(row["delta_lots"]), 0) * row["one_lot_value"] for row in target_rows
    )
    return {
        "available_cash": available_cash,
        "buying_power_after_sells": buying_power_after_sells,
        "estimated_cash_after_orders": available_cash + gross_sell - gross_buy,
        "conservative_cash_after_orders": (
            available_cash
            + gross_sell * (1 - cash_buffer_pct)
            - gross_buy * (1 + cash_buffer_pct)
        ),
        "planned_target_positions": len(
            [row for row in target_rows if int(row["target_lots"]) > 0]
        ),
        "below_one_lot_target_positions": len(
            [
                row
                for row in target_rows
                if row["target_weight"] > 1e-12 and int(row["model_target_lots"]) == 0
            ]
        ),
        "cash_limited_target_positions": len(
            [row for row in target_rows if row.get("constraint") == "cash_limited"]
        ),
        "below_min_order_positions": len(
            [row for row in target_rows if row.get("constraint") == "below_min_order"]
        ),
        "minimum_one_lot_cost": sum(
            row["one_lot_value"] for row in target_rows if row["target_weight"] > 1e-12
        ),
        "lot_rounding_unallocated_value": sum(
            max(
                row["target_value"]
                - int(row["model_target_lots"]) * row["one_lot_value"],
                0.0,
            )
            for row in target_rows
            if row["target_weight"] > 1e-12
        ),
        "cash_buffer_pct": cash_buffer_pct,
    }


def resolve_available_cash(
    account_overview: dict[str, Any],
    *,
    currency: str,
    portfolio_value: float,
    target_rows: list[dict[str, Any]],
) -> float:
    summary = account_overview.get("summary") or {}
    normalized_currency = currency.strip().lower()
    money_rows = summary.get("money") or []
    matching_money = [
        row
        for row in money_rows
        if str((row or {}).get("currency") or "").strip().lower() == normalized_currency
    ]
    if matching_money:
        total = sum(
            safe_float((row or {}).get("value")) or 0.0 for row in matching_money
        )
        blocked = sum(
            safe_float((row or {}).get("value")) or 0.0
            for row in summary.get("blocked_money") or []
            if str((row or {}).get("currency") or "").strip().lower()
            == normalized_currency
        )
        return max(total - blocked, 0.0)

    invested = sum(
        max(safe_float(row.get("current_value")) or 0.0, 0.0) for row in target_rows
    )
    return max(portfolio_value - invested, 0.0)


def build_execution_warnings(cash_plan: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    below_one_lot = int(cash_plan["below_one_lot_target_positions"])
    if below_one_lot:
        warnings.append(
            f"Для {below_one_lot} целей сумма по весу меньше стоимости одного брокерского лота."
        )
    cash_limited = int(cash_plan["cash_limited_target_positions"])
    if cash_limited:
        warnings.append(
            f"Доступные деньги и резерв исполнения уменьшили план для {cash_limited} целей."
        )
    below_minimum = int(cash_plan["below_min_order_positions"])
    if below_minimum:
        warnings.append(
            f"Для {below_minimum} целей дельта ниже заданной минимальной суммы заявки."
        )
    return warnings


def build_execution_blocking_reasons(
    *,
    account_overview: dict[str, Any],
    settings: StrategyRunSettings,
    target_rows: list[dict[str, Any]],
    orders: list[dict[str, Any]],
    unpriced_positions: list[str],
) -> list[str]:
    reasons: list[str] = []
    if settings.order_type != "market":
        reasons.append(
            "Исполнение модели поддерживает только рыночные заявки; пересчитайте план в режиме market."
        )

    open_orders = int(
        safe_float((account_overview.get("summary") or {}).get("open_orders_count"))
        or 0
    )
    if open_orders:
        reasons.append(
            f"На счете есть открытые заявки: {open_orders}. Перед исполнением их нужно завершить или отменить."
        )

    if unpriced_positions:
        reasons.append(
            "Нет пригодной цены для текущих или целевых позиций: "
            + ", ".join(sorted(set(unpriced_positions)))
            + "."
        )

    missing_instruments = sorted(
        {str(row["ticker"]) for row in orders if not row.get("instrument_id")}
    )
    if missing_instruments:
        reasons.append(
            "Нет брокерских идентификаторов инструментов: "
            + ", ".join(missing_instruments)
            + "."
        )

    targets_by_ticker = {str(row["ticker"]): row for row in target_rows}
    unavailable_api = sorted(
        str(order["ticker"])
        for order in orders
        if (targets_by_ticker.get(str(order["ticker"])) or {}).get(
            "api_trade_available_flag"
        )
        is False
    )
    unavailable_market = sorted(
        str(order["ticker"])
        for order in orders
        if (targets_by_ticker.get(str(order["ticker"])) or {}).get(
            "market_order_available_flag"
        )
        is False
    )
    unavailable_buys = sorted(
        str(order["ticker"])
        for order in orders
        if order["side"] == "buy"
        and (targets_by_ticker.get(str(order["ticker"])) or {}).get(
            "buy_available_flag"
        )
        is False
    )
    unavailable_sells = sorted(
        str(order["ticker"])
        for order in orders
        if order["side"] == "sell"
        and (targets_by_ticker.get(str(order["ticker"])) or {}).get(
            "sell_available_flag"
        )
        is False
    )
    if unavailable_api:
        reasons.append(
            "Торговля через API недоступна для: " + ", ".join(unavailable_api) + "."
        )
    if unavailable_market:
        reasons.append(
            "Рыночные заявки недоступны для: " + ", ".join(unavailable_market) + "."
        )
    if unavailable_buys:
        reasons.append("Покупка недоступна для: " + ", ".join(unavailable_buys) + ".")
    if unavailable_sells:
        reasons.append("Продажа недоступна для: " + ", ".join(unavailable_sells) + ".")

    blocked_sells = sorted(
        str(order["ticker"])
        for order in orders
        if order["side"] == "sell"
        and int(order["quantity_lots"])
        > int(
            (targets_by_ticker.get(str(order["ticker"])) or {}).get("available_lots")
            or 0
        )
    )
    if blocked_sells:
        reasons.append(
            "Недостаточно незаблокированных лотов для продажи: "
            + ", ".join(blocked_sells)
            + "."
        )

    return reasons


def build_plan_id(payload: dict[str, Any]) -> str:
    plan = {
        "account_id": payload.get("account_id"),
        "strategy_name": payload.get("strategy_name"),
        "run_time": payload.get("run_time"),
        "settings": payload.get("settings"),
        "portfolio": payload.get("portfolio"),
        "target_weights": payload.get("target_weights"),
        "orders": payload.get("orders"),
    }
    serialized = json.dumps(
        plan,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def build_current_position_map(
    account_overview: dict[str, Any],
    stock_by_figi: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    portfolio = account_overview.get("sections", {}).get("portfolio") or {}
    positions = portfolio.get("positions") or []
    stock_by_uid = {
        str(item.get("uid") or item.get("instrument_uid")): item
        for item in stock_by_figi.values()
        if item.get("uid") or item.get("instrument_uid")
    }
    result: dict[str, dict[str, Any]] = {}
    for position in positions:
        figi = str(position.get("figi") or "")
        instrument_type = str(position.get("instrument_type") or "").lower()
        if instrument_type == "currency" or figi.upper() == "RUB000UTSTOM":
            continue
        instrument_uid = str(position.get("instrument_uid") or "")
        stock = stock_by_figi.get(figi) or stock_by_uid.get(instrument_uid, {})
        ticker = str(position.get("ticker") or stock.get("ticker") or figi)
        if not ticker:
            continue
        lot = int(safe_float(stock.get("lot")) or 1)
        quantity = amount_value(position.get("quantity"))
        lots = amount_value(position.get("quantity_lots"))
        if lots is None and quantity is not None and lot > 0:
            lots = quantity / lot
        result[ticker] = {
            "figi": figi,
            "instrument_uid": instrument_uid or stock.get("uid"),
            "name": stock.get("name"),
            "instrument_type": instrument_type,
            "quantity": quantity or 0.0,
            "lots": lots or 0.0,
            "blocked_lots": amount_value(position.get("blocked_lots")) or 0.0,
        }
    return result


def resolve_portfolio_value(
    account_overview: dict[str, Any],
    current_positions: dict[str, dict[str, Any]],
) -> float:
    summary = account_overview.get("summary") or {}
    value = safe_float(summary.get("portfolio_value"))
    if is_positive(value):
        return float(value)
    total = 0.0
    for money in summary.get("money") or []:
        total += safe_float((money or {}).get("value")) or 0.0
    return total


def primary_currency(account_overview: dict[str, Any]) -> str:
    summary = account_overview.get("summary") or {}
    total = summary.get("total_amount_portfolio") or {}
    return str(total.get("currency") or "rub")


def build_order_row(
    row: dict[str, Any], settings: StrategyRunSettings
) -> dict[str, Any]:
    side = "buy" if row["delta_lots"] > 0 else "sell"
    price = row["last_price"]
    limit_price = None
    if settings.order_type == "limit":
        multiplier = (
            1 + settings.limit_offset_pct
            if side == "buy"
            else 1 - settings.limit_offset_pct
        )
        limit_price = round(price * multiplier, 6)

    return {
        "ticker": row["ticker"],
        "figi": row["figi"],
        "instrument_id": row["instrument_id"],
        "name": row["name"],
        "side": side,
        "order_type": settings.order_type,
        "quantity_lots": abs(int(row["delta_lots"])),
        "lot": row["lot"],
        "last_price": price,
        "limit_price": limit_price,
        "estimated_amount": abs(row["delta_lots"]) * row["lot"] * price,
        "target_weight": row["target_weight"],
        "current_weight": row["current_weight"],
    }


def build_stop_rows(row: dict[str, Any], strategy: Any) -> list[dict[str, Any]]:
    policy = getattr(strategy, "exit_policy", None)
    stop_loss_pct = safe_float(getattr(policy, "stop_loss_pct", None))
    take_profit_pct = safe_float(getattr(policy, "take_profit_pct", None))
    rows: list[dict[str, Any]] = []
    if is_positive(stop_loss_pct):
        rows.append(
            build_stop_row(
                row,
                kind="stop_loss",
                trigger_price=row["last_price"] * (1 - float(stop_loss_pct)),
                pct=float(stop_loss_pct),
            )
        )
    if is_positive(take_profit_pct):
        rows.append(
            build_stop_row(
                row,
                kind="take_profit",
                trigger_price=row["last_price"] * (1 + float(take_profit_pct)),
                pct=float(take_profit_pct),
            )
        )
    return rows


def build_stop_row(
    row: dict[str, Any],
    *,
    kind: str,
    trigger_price: float,
    pct: float,
) -> dict[str, Any]:
    return {
        "ticker": row["ticker"],
        "figi": row["figi"],
        "instrument_id": row["instrument_id"],
        "name": row["name"],
        "kind": kind,
        "side": "sell",
        "quantity_lots": int(row["target_lots"]),
        "stop_price": round(trigger_price, 6),
        "distance_pct": pct,
        "last_price": row["last_price"],
    }


def amount_value(value: Any) -> float | None:
    if isinstance(value, dict):
        return safe_float(value.get("value"))
    return safe_float(value)


def safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if np.isfinite(result) else None


def is_positive(value: float | None) -> bool:
    return value is not None and np.isfinite(value) and value > 0
