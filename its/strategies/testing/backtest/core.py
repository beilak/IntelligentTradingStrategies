from __future__ import annotations

import json
import os
import re
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import HTTPException

from its.strategies.testing.backtest.vectorbt_backtest import (
    backtest_strategies_vectorbt,
)
from its.strategies.testing.cpcv import (
    load_registered_model,
    safe_float,
    timestamp_to_string,
)

CACHE_DIR = Path(
    os.getenv("STRATEGY_BACKTEST_CACHE_DIR", "/app/its/data/strategy_tests/backtest")
)


def generate_backtest_report(
    model_name: str,
    stocks: list[dict[str, Any]],
    prices: pd.DataFrame,
    settings: dict[str, Any],
) -> dict[str, Any]:
    model_cls = load_registered_model(model_name)
    if prices.empty:
        raise HTTPException(status_code=404, detail="No prices found for Backtesting.")

    close = build_close_prices(prices)
    strategy = model_cls(prices, pd.DataFrame(stocks)).build()
    trading_start_date = pd.Timestamp(
        settings.get("trading_start_date") or settings.get("start_date")
    )
    if trading_start_date < close.index.min():
        trading_start_date = close.index.min()
        settings["trading_start_date"] = timestamp_to_string(trading_start_date)
    if trading_start_date > close.index.max():
        raise HTTPException(
            status_code=422,
            detail="trading_start_date must be inside the loaded price period.",
        )

    results = backtest_strategies_vectorbt(
        strategies={strategy.name: strategy},
        prices=close,
        rebalance_freq=settings.get("rebalance_freq", "3ME"),
        rebalance_on=settings.get("rebalance_on", "last"),
        trading_start_date=trading_start_date,
        fees=settings.get("fees", 0.0008),
        slippage=settings.get("slippage", 0.0),
        freq=settings.get("freq", "1D"),
        init_cash=settings.get("init_cash", 1_000_000.0),
    )
    backtest_result = results[strategy.name]
    portfolio = backtest_result.portfolio
    value = portfolio.value()
    returns = portfolio.returns()
    drawdown = value / value.cummax() - 1
    rolling_window = int(settings.get("rolling_window", 252))
    rolling_sharpe = build_rolling_sharpe(returns, rolling_window)
    total_return = safe_float(portfolio.total_return())
    tax_rate = float(settings.get("tax_rate", 0.13))

    return {
        "metadata": {
            "model_name": model_name,
            "strategy_name": strategy.name,
            "strategy_description": strategy.description,
            "test_name": settings.get("test_name", ""),
            "test_type": "Backtesting",
            "generated_at": datetime.now(UTC).isoformat(),
            "settings": settings,
            "price_period": {
                "start": timestamp_to_string(close.index.min()),
                "end": timestamp_to_string(close.index.max()),
                "rows": len(close),
            },
            "trading_period": {
                "start": timestamp_to_string(value.index.min()),
                "end": timestamp_to_string(value.index.max()),
                "rows": len(value),
            },
            "assets": [
                {
                    "figi": item.get("figi"),
                    "ticker": item.get("ticker"),
                    "name": item.get("name"),
                }
                for item in stocks
                if item.get("ticker") in set(close.columns)
            ],
            "asset_count": len(close.columns),
        },
        "report": backtest_stats_to_rows(portfolio.stats()),
        "summary": [
            {"metric": "Total Return", "value": format_percent(total_return), "numeric_value": total_return},
            {
                "metric": "After Tax Return",
                "value": format_percent(total_return * (1 - tax_rate) if total_return is not None else None),
                "numeric_value": total_return * (1 - tax_rate) if total_return is not None else None,
            },
            {
                "metric": "Max Drawdown",
                "value": format_percent(safe_float(portfolio.drawdowns.max_drawdown())),
                "numeric_value": safe_float(portfolio.drawdowns.max_drawdown()),
            },
            {
                "metric": "Max Drawdown Duration",
                "value": str(portfolio.drawdowns.duration.max()),
                "numeric_value": safe_float(portfolio.drawdowns.duration.max()),
            },
        ],
        "equity_curve": series_to_curve("Equity Curve", value),
        "drawdown_curve": series_to_curve("Drawdown", drawdown),
        "rolling_sharpe": series_to_curve("Rolling Sharpe", rolling_sharpe),
        "rebalance_weights": weights_to_records(backtest_result.weights),
    }


def build_close_prices(prices: pd.DataFrame) -> pd.DataFrame:
    required_columns = {"time", "ticker", "close"}
    missing = required_columns.difference(prices.columns)
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Prices payload is missing columns: {', '.join(sorted(missing))}.",
        )
    prices = prices.copy()
    prices["time"] = pd.to_datetime(prices["time"], errors="coerce")
    prices["close"] = pd.to_numeric(prices["close"], errors="coerce")
    prices = prices.dropna(subset=["time", "ticker", "close"])
    close = (
        prices.pivot_table(index="time", columns="ticker", values="close", aggfunc="last")
        .sort_index()
        .replace(0, pd.NA)
        .ffill()
        .dropna(axis=1, how="all")
    )
    close = close.loc[:, close.nunique(dropna=True) > 1]
    if close.empty:
        raise HTTPException(status_code=422, detail="Close price matrix is empty.")
    return close


def build_rolling_sharpe(returns: pd.Series, window: int) -> pd.Series:
    if window <= 1:
        window = 2
    return returns.rolling(window).apply(
        lambda item: item.mean() / item.std() * (252**0.5) if item.std() else 0,
        raw=False,
    )


def series_to_curve(name: str, series: pd.Series) -> dict[str, Any]:
    clean = series.dropna()
    return {
        "name": name,
        "points": [
            {"time": timestamp_to_string(index), "value": float(value)}
            for index, value in clean.items()
        ],
        "final_value": float(clean.iloc[-1]) if not clean.empty else None,
    }


def weights_to_records(weights: pd.DataFrame) -> list[dict[str, Any]]:
    records = []
    clean = weights.dropna(how="all").fillna(0)
    for index, row in clean.iterrows():
        non_zero = row[row.abs() > 1e-12].sort_values(ascending=False)
        records.append(
            {
                "time": timestamp_to_string(index),
                "total_weight": float(non_zero.sum()),
                "asset_count": int(len(non_zero)),
                "weights": [
                    {"ticker": ticker, "weight": float(weight)}
                    for ticker, weight in non_zero.items()
                ],
            }
        )
    return records


def backtest_stats_to_rows(stats: pd.Series) -> list[dict[str, Any]]:
    rows = []
    for metric, value in stats.items():
        rows.append(
            {
                "metric": str(metric),
                "value": format_stat_value(str(metric), value),
                "numeric_value": safe_float(value),
            }
        )
    return rows


def format_stat_value(metric: str, value: Any) -> str:
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return timestamp_to_string(value)
    numeric = safe_float(value)
    if numeric is None:
        return str(value)
    if "[%]" in metric:
        return f"{numeric:.2f}%"
    lower_metric = metric.lower()
    if any(word in lower_metric for word in ("value", "cash", "fees", "paid", "profit", "loss")):
        return f"{numeric:,.2f}".replace(",", " ")
    if any(word in lower_metric for word in ("return", "rate", "drawdown")):
        return f"{numeric:.2%}"
    if abs(numeric) >= 1000:
        return f"{numeric:,.2f}".replace(",", " ")
    return f"{numeric:.4g}"


def format_percent(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.2%}"


def list_test_paths(model_name: str) -> list[Path]:
    prefix = f"{safe_name(model_name)}_"
    suffix = "_backtest.json"
    if not CACHE_DIR.exists():
        return []
    return sorted(
        path for path in CACHE_DIR.glob(f"{prefix}*{suffix}") if path.is_file()
    )


def read_test_summary(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    metadata = payload.get("metadata", {})
    return {
        "file_name": path.name,
        "test_name": metadata.get("test_name", path.stem),
        "model_name": metadata.get("model_name", ""),
        "generated_at": metadata.get("generated_at", ""),
        "settings": metadata.get("settings", {}),
        "trading_period": metadata.get("trading_period", {}),
        "asset_count": metadata.get("asset_count", 0),
    }


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=500, detail="Cached Backtesting file is invalid."
        ) from exc


def cache_path(model_name: str, test_name: str) -> Path:
    return CACHE_DIR / f"{safe_name(model_name)}_{safe_name(test_name)}_backtest.json"


def safe_name(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return normalized.strip("._") or "unnamed"
