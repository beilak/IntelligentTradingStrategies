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
from its.strategies_model.core.trading_strategy import TradingStrategy

CACHE_DIR = Path(
    os.getenv("STRATEGY_BACKTEST_CACHE_DIR", "/app/its/data/strategy_tests/backtest")
)


def generate_backtest_report(
    model_name: str,
    stocks: list[dict[str, Any]],
    prices: pd.DataFrame,
    settings: dict[str, Any],
    dividends_info: pd.DataFrame | None = None,
) -> dict[str, Any]:
    model_cls = load_registered_model(model_name)
    if prices.empty:
        raise HTTPException(status_code=404, detail="No prices found for Backtesting.")

    close = build_close_prices(prices)
    strategy = model_cls(
        prices,
        pd.DataFrame(stocks),
        _dividends_info=dividends_info,
    ).build()
    trading_start_date = normalize_timestamp_for_index(
        settings.get("trading_start_date") or settings.get("start_date"),
        close.index,
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
        rebalance_freq=settings["rebalance_freq"],
        rebalance_on=settings["rebalance_on"],
        trading_start_date=trading_start_date,
        fees=settings["fees"],
        slippage=settings["slippage"],
        freq=settings["freq"],
        init_cash=settings["init_cash"],
    )
    return build_backtest_payload(
        model_name=model_name,
        strategy_name=strategy.name,
        strategy_description=strategy.description,
        stocks=stocks,
        close=close,
        settings=settings,
        backtest_result=results[strategy.name],
    )


def generate_trading_strategy_backtest_report(
    strategy_name: str,
    stocks: list[dict[str, Any]],
    prices: pd.DataFrame,
    settings: dict[str, Any],
    dividends_info: pd.DataFrame | None = None,
) -> dict[str, Any]:
    strategy_cls = load_registered_trading_strategy(strategy_name)
    if prices.empty:
        raise HTTPException(status_code=404, detail="No prices found for Backtesting.")

    close = build_close_prices(prices)
    open_prices = build_price_matrix(prices, "open", close)
    high = build_price_matrix(prices, "high", close)
    low = build_price_matrix(prices, "low", close)
    trading_strategy: TradingStrategy = strategy_cls(
        prices,
        pd.DataFrame(stocks),
        _dividends_info=dividends_info,
    ).build()
    trading_start_date = normalize_timestamp_for_index(
        settings.get("trading_start_date") or settings.get("start_date"),
        close.index,
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
        strategies={trading_strategy.name: trading_strategy},
        prices=close,
        open=open_prices,
        high=high,
        low=low,
        rebalance_freq=settings["rebalance_freq"],
        rebalance_on=settings["rebalance_on"],
        trading_start_date=trading_start_date,
        fees=settings["fees"],
        slippage=settings["slippage"],
        freq=settings["freq"],
        init_cash=settings["init_cash"],
    )
    return build_backtest_payload(
        model_name=strategy_name,
        strategy_name=trading_strategy.name,
        strategy_description=trading_strategy.description,
        stocks=stocks,
        close=close,
        settings=settings,
        backtest_result=results[trading_strategy.name],
        extra_metadata={
            "entity_type": "trading_strategy",
            "core_strategy_name": trading_strategy.core.name,
            "core_strategy_description": trading_strategy.core.description,
            "exit_policy": {
                "name": trading_strategy.exit_policy.name,
                "description": trading_strategy.exit_policy.description,
            },
            "strategy_metadata": dict(trading_strategy.metadata),
        },
    )


def build_backtest_payload(
    *,
    model_name: str,
    strategy_name: str,
    strategy_description: str,
    stocks: list[dict[str, Any]],
    close: pd.DataFrame,
    settings: dict[str, Any],
    backtest_result: Any,
    extra_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    portfolio = backtest_result.portfolio
    value = portfolio.value()
    returns = portfolio.returns()
    drawdown = value / value.cummax() - 1
    rolling_window = int(settings.get("rolling_window", 252))
    rolling_sharpe = build_rolling_sharpe(returns, rolling_window)
    total_return = safe_float(portfolio.total_return())
    tax_rate = float(settings.get("tax_rate", 0.13))
    execution_events = execution_events_to_records(backtest_result.execution_events)
    pnl_source = build_backtest_pnl_source(
        backtest_result=backtest_result,
        settings=settings,
    )

    result = {
        "metadata": {
            "model_name": model_name,
            "strategy_name": strategy_name,
            "strategy_description": strategy_description,
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
                    "sector": item.get("sector"),
                }
                for item in stocks
                if item.get("ticker") in set(close.columns)
            ],
            "asset_count": len(close.columns),
            **(extra_metadata or {}),
        },
        "report": backtest_stats_to_rows(portfolio.stats()),
        "summary": [
            {
                "metric": "Total Return",
                "value": format_percent(total_return),
                "numeric_value": total_return,
            },
            {
                "metric": "After Tax Return",
                "value": format_percent(
                    total_return * (1 - tax_rate) if total_return is not None else None
                ),
                "numeric_value": (
                    total_return * (1 - tax_rate) if total_return is not None else None
                ),
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
            {
                "metric": "Stop/Take Exits",
                "value": str(len(execution_events)),
                "numeric_value": float(len(execution_events)),
            },
        ],
        "equity_curve": series_to_curve("Equity Curve", value),
        "drawdown_curve": series_to_curve("Drawdown", drawdown),
        "rolling_sharpe": series_to_curve("Rolling Sharpe", rolling_sharpe),
        "pnl_source": pnl_source,
        "rebalance_weights": weights_to_records(backtest_result.weights, stocks),
        "execution_events": execution_events,
    }
    return enrich_backtest_payload_with_stocks(result, stocks)


def normalize_timestamp_for_index(value: Any, index: pd.Index) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if pd.isna(timestamp):
        raise HTTPException(status_code=422, detail="trading_start_date is invalid.")

    index_tz = getattr(index, "tz", None)
    if index_tz is None:
        if timestamp.tzinfo is not None:
            return timestamp.tz_localize(None)
        return timestamp

    if timestamp.tzinfo is None:
        return timestamp.tz_localize(index_tz)
    return timestamp.tz_convert(index_tz)


def build_close_prices(prices: pd.DataFrame) -> pd.DataFrame:
    required_columns = {"time", "ticker", "close"}
    missing = required_columns.difference(prices.columns)

    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Prices payload is missing columns: {', '.join(sorted(missing))}.",
        )

    prices = prices.copy()

    prices["time"] = pd.to_datetime(
        prices["time"],
        errors="coerce",
        utc=True,
    ).dt.tz_localize(None)

    prices["close"] = pd.to_numeric(
        prices["close"],
        errors="coerce",
    )

    prices = prices.dropna(subset=["time", "ticker", "close"])

    close = (
        prices.pivot_table(
            index="time",
            columns="ticker",
            values="close",
            aggfunc="last",
        )
        .sort_index()
        .replace(0, pd.NA)
        .ffill()
        .dropna(axis=1, how="all")
    )

    close = close.loc[:, close.nunique(dropna=True) > 1]

    if close.empty:
        raise HTTPException(
            status_code=422,
            detail="Close price matrix is empty.",
        )

    return close


def build_price_matrix(
    prices: pd.DataFrame,
    price_column: str,
    base: pd.DataFrame,
) -> pd.DataFrame:
    if price_column not in prices.columns:
        return base.copy()

    prices = prices.copy()
    prices["time"] = pd.to_datetime(
        prices["time"],
        errors="coerce",
        utc=True,
    ).dt.tz_localize(None)
    prices[price_column] = pd.to_numeric(prices[price_column], errors="coerce")
    prices = prices.dropna(subset=["time", "ticker", price_column])
    matrix = (
        prices.pivot_table(
            index="time",
            columns="ticker",
            values=price_column,
            aggfunc="last",
        )
        .sort_index()
        .replace(0, pd.NA)
    )
    matrix = matrix.reindex(index=base.index, columns=base.columns)
    return matrix.where(matrix.notna(), base)


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


def build_backtest_pnl_source(
    *,
    backtest_result: Any,
    settings: dict[str, Any],
) -> dict[str, Any]:
    """Return compact replay data for a PnL report over any backtest sub-period.

    Portfolio-level PnL can be reconstructed from the existing equity curve.  This
    source additionally preserves sparse per-asset daily contributions and order /
    trade records so the UI can calculate exact attribution for a user-selected
    interval without rerunning the model.
    """

    portfolio = backtest_result.portfolio
    asset_values = portfolio.asset_value(group_by=False)
    if isinstance(asset_values, pd.Series):
        asset_values = asset_values.to_frame()
    asset_values = asset_values.fillna(0.0)

    asset_cash_flows = pd.DataFrame(
        0.0,
        index=asset_values.index,
        columns=asset_values.columns,
    )
    orders = backtest_orders_to_records(
        portfolio=portfolio,
        order_prices=backtest_result.order_prices,
    )
    for order in orders:
        timestamp = pd.Timestamp(order["time"])
        ticker = order["ticker"]
        if timestamp not in asset_cash_flows.index or ticker not in asset_cash_flows:
            continue
        gross_value = order["size"] * order["price"]
        cash_flow = (
            -(gross_value + order["fees"])
            if order["side"] == "buy"
            else gross_value - order["fees"]
        )
        asset_cash_flows.at[timestamp, ticker] += cash_flow

    asset_value_changes = asset_values.diff()
    if not asset_value_changes.empty:
        asset_value_changes.iloc[0] = asset_values.iloc[0]
    daily_contributions = asset_value_changes + asset_cash_flows

    return {
        "method": "vectorbt order replay + daily mark-to-market",
        "currency": "RUB",
        "initial_nav": float(settings.get("init_cash", 0.0)),
        "external_flows": False,
        "taxes_applied": False,
        "daily_asset_pnl": dataframe_to_sparse_records(daily_contributions),
        "orders": orders,
        "trades": backtest_trades_to_records(portfolio),
    }


def dataframe_to_sparse_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for timestamp, row in frame.iterrows():
        contributions = {
            str(ticker): float(value)
            for ticker, value in row.items()
            if pd.notna(value) and abs(float(value)) > 1e-12
        }
        if contributions:
            records.append(
                {
                    "time": timestamp_to_string(timestamp),
                    "contributions": contributions,
                }
            )
    return records


def backtest_orders_to_records(
    *,
    portfolio: Any,
    order_prices: pd.DataFrame,
) -> list[dict[str, Any]]:
    readable = portfolio.orders.records_readable
    records: list[dict[str, Any]] = []
    for _, row in readable.iterrows():
        timestamp = pd.Timestamp(row["Timestamp"])
        ticker = str(row["Column"])
        side = str(row["Side"]).lower()
        size = float(row["Size"])
        price = float(row["Price"])
        fees = float(row["Fees"])
        reference_price = frame_value(order_prices, timestamp, ticker)
        slippage_cost = 0.0
        if reference_price is not None:
            slippage_cost = max(
                0.0,
                size
                * (
                    price - reference_price
                    if side == "buy"
                    else reference_price - price
                ),
            )
        records.append(
            {
                "id": int(row["Order Id"]),
                "time": timestamp_to_string(timestamp),
                "ticker": ticker,
                "side": side,
                "size": size,
                "price": price,
                "fees": fees,
                "reference_price": reference_price,
                "slippage_cost": slippage_cost,
            }
        )
    return records


def backtest_trades_to_records(portfolio: Any) -> list[dict[str, Any]]:
    readable = portfolio.trades.records_readable
    records: list[dict[str, Any]] = []
    for _, row in readable.iterrows():
        records.append(
            {
                "id": int(row["Exit Trade Id"]),
                "ticker": str(row["Column"]),
                "size": float(row["Size"]),
                "entry_time": timestamp_to_string(row["Entry Timestamp"]),
                "exit_time": timestamp_to_string(row["Exit Timestamp"]),
                "pnl": safe_float(row["PnL"]),
                "return": safe_float(row["Return"]),
                "status": str(row["Status"]).lower(),
            }
        )
    return records


def frame_value(
    frame: pd.DataFrame,
    timestamp: pd.Timestamp,
    ticker: str,
) -> float | None:
    if timestamp not in frame.index or ticker not in frame.columns:
        return None
    return safe_float(frame.at[timestamp, ticker])


def weights_to_records(
    weights: pd.DataFrame,
    stocks: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    stock_by_ticker = {
        str(item.get("ticker")): item for item in stocks or [] if item.get("ticker")
    }
    records = []
    clean = weights.dropna(how="all").fillna(0)
    for index, row in clean.iterrows():
        non_zero = row[row.abs() > 1e-12].sort_values(ascending=False)
        records.append(
            {
                "time": timestamp_to_string(index),
                "total_weight": float(non_zero.sum()),
                "asset_count": len(non_zero),
                "weights": [
                    {
                        "ticker": ticker,
                        "weight": float(weight),
                        "sector": stock_by_ticker.get(str(ticker), {}).get("sector"),
                    }
                    for ticker, weight in non_zero.items()
                ],
            }
        )
    return records


def enrich_backtest_payload_with_stocks(
    payload: dict[str, Any],
    stocks: list[dict[str, Any]],
) -> dict[str, Any]:
    stock_by_ticker = {
        str(item.get("ticker")): item for item in stocks if item.get("ticker")
    }
    metadata = payload.get("metadata", {})

    for asset in metadata.get("assets", []):
        ticker = str(asset.get("ticker") or "")
        stock = stock_by_ticker.get(ticker)
        if stock and not asset.get("sector"):
            asset["sector"] = stock.get("sector")

    for record in payload.get("rebalance_weights", []):
        for weight in record.get("weights", []):
            ticker = str(weight.get("ticker") or "")
            stock = stock_by_ticker.get(ticker)
            if stock and not weight.get("sector"):
                weight["sector"] = stock.get("sector")

    return payload


def execution_events_to_records(events: pd.DataFrame) -> list[dict[str, Any]]:
    if events is None or events.empty:
        return []

    records = []
    for _, row in events.sort_values(["time", "ticker"]).iterrows():
        records.append(
            {
                "time": timestamp_to_string(row["time"]),
                "ticker": str(row["ticker"]),
                "reason": str(row["reason"]),
                "entry_time": timestamp_to_string(row["entry_time"]),
                "entry_price": safe_float(row["entry_price"]),
                "execution_price": safe_float(row["execution_price"]),
                "threshold_price": safe_float(row["threshold_price"]),
                "return_pct": safe_float(row["return_pct"]),
                "weight": safe_float(row["weight"]),
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
    if any(
        word in lower_metric
        for word in ("value", "cash", "fees", "paid", "profit", "loss")
    ):
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


def load_registered_trading_strategy(strategy_name: str) -> type[Any]:
    import importlib
    import sys

    module_name = "its.strategies_model.model"
    for name in sorted(sys.modules, reverse=True):
        if name == module_name or name.startswith(f"{module_name}."):
            del sys.modules[name]
    module = importlib.import_module(module_name)
    registered_names = set(getattr(module, "__all__", []))
    if strategy_name not in registered_names:
        raise HTTPException(
            status_code=404, detail="Trading strategy is not registered."
        )
    strategy_cls = getattr(module, strategy_name, None)
    if strategy_cls is None:
        raise HTTPException(
            status_code=404, detail="Trading strategy is not available."
        )
    return strategy_cls
