from __future__ import annotations

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

    target_rows: list[dict[str, Any]] = []
    orders: list[dict[str, Any]] = []
    stop_orders: list[dict[str, Any]] = []

    tickers = sorted(
        set(latest_prices.index.astype(str))
        | set(target_weights.index.astype(str))
        | set(current_positions)
    )
    for ticker in tickers:
        stock = stock_by_ticker.get(ticker, {})
        price = safe_float(latest_prices.get(ticker))
        if not is_positive(price):
            continue

        lot = int(safe_float(stock.get("lot")) or 1)
        lot = max(lot, 1)
        current = current_positions.get(ticker, {})
        current_lots = safe_float(current.get("lots")) or 0.0
        current_quantity = safe_float(current.get("quantity")) or current_lots * lot
        current_value = current_quantity * price
        current_weight = current_value / portfolio_value if portfolio_value else 0.0
        target_weight = safe_float(target_weights.get(ticker)) or 0.0
        if not np.isfinite(target_weight) or abs(target_weight) < 1e-12:
            target_weight = 0.0
        target_value = max(target_weight, 0.0) * portfolio_value
        target_lots = int(target_value // (price * lot)) if price * lot > 0 else 0
        delta_lots = target_lots - int(round(current_lots))
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
            "last_price": price,
            "current_lots": current_lots,
            "current_quantity": current_quantity,
            "current_value": current_value,
            "current_weight": current_weight,
            "target_weight": target_weight,
            "target_value": target_value,
            "target_lots": target_lots,
            "delta_lots": delta_lots,
            "delta_value": delta_value,
        }

        if target_weight > 1e-12 or abs(current_lots) > 1e-12 or abs(delta_lots) > 0:
            target_rows.append(row)

        if abs(delta_lots) > 0 and abs(delta_value) >= settings.min_order_value:
            orders.append(build_order_row(row, settings))

        if target_lots > 0:
            stop_orders.extend(build_stop_rows(row, strategy))

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
    return {
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
        },
        "portfolio": {
            "value": portfolio_value,
            "currency": primary_currency(account_overview),
        },
        "summary": {
            "target_positions": len(
                [row for row in target_rows if row["target_weight"] > 1e-12]
            ),
            "orders": len(orders),
            "buy_orders": len([item for item in orders if item["side"] == "buy"]),
            "sell_orders": len([item for item in orders if item["side"] == "sell"]),
            "stop_orders": len(stop_orders),
            "gross_buy": gross_buy,
            "gross_sell": gross_sell,
            "net_cash_need": gross_buy - gross_sell,
        },
        "target_weights": target_rows,
        "orders": orders,
        "stop_orders": stop_orders,
    }


def build_current_position_map(
    account_overview: dict[str, Any],
    stock_by_figi: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    portfolio = account_overview.get("sections", {}).get("portfolio") or {}
    positions = portfolio.get("positions") or []
    result: dict[str, dict[str, Any]] = {}
    for position in positions:
        figi = str(position.get("figi") or "")
        stock = stock_by_figi.get(figi, {})
        ticker = str(position.get("ticker") or stock.get("ticker") or "")
        if not ticker:
            continue
        lot = int(safe_float(stock.get("lot")) or 1)
        quantity = amount_value(position.get("quantity"))
        lots = amount_value(position.get("quantity_lots"))
        if lots is None and quantity is not None and lot > 0:
            lots = quantity / lot
        result[ticker] = {
            "figi": figi,
            "instrument_uid": position.get("instrument_uid") or stock.get("uid"),
            "name": stock.get("name"),
            "quantity": quantity or 0.0,
            "lots": lots or 0.0,
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
