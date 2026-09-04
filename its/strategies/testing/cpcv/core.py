from __future__ import annotations

import importlib
import json
import math
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from fastapi import HTTPException
from skfolio import Population
from skfolio.model_selection import CombinatorialPurgedCV
from skfolio.portfolio import MultiPeriodPortfolio, Portfolio
from sklearn.base import clone

from its.strategies.core.types.strategy_types import Strategy

CACHE_DIR = Path(
    os.getenv("STRATEGY_TEST_CACHE_DIR", "/app/its/data/strategy_tests/cpcv")
)


def generate_cpcv_report(
    model_name: str,
    stocks: list[dict[str, Any]],
    prices: pd.DataFrame,
    settings: dict[str, Any],
    dividends_info: pd.DataFrame | None = None,
) -> dict[str, Any]:
    model_cls = load_registered_model(model_name)
    figis = [item["figi"] for item in stocks if item.get("figi")]
    if not figis:
        raise HTTPException(status_code=404, detail="No assets found for CPCV.")

    if prices.empty:
        raise HTTPException(status_code=404, detail="No prices found for CPCV.")

    returns = build_returns_matrix(prices)
    n_folds = settings.get("n_folds", 10)
    if len(returns) < n_folds + 2:
        raise HTTPException(
            status_code=422,
            detail="Not enough price rows for selected CPCV settings.",
        )

    test_size = settings.get("test_size", 0.33)
    split_index = max(1, int(len(returns) * (1 - test_size)))
    if len(returns) - split_index < n_folds:
        split_index = len(returns) - n_folds
    if split_index <= 0:
        raise HTTPException(
            status_code=422,
            detail="Not enough rows to build train/test split.",
        )

    x_train = returns.iloc[:split_index]
    x_test = returns.iloc[split_index:]

    strategy = model_cls(
        prices,
        pd.DataFrame(stocks),
        _dividends_info=dividends_info,
    ).build()
    validation_pipeline = clone(strategy.pipeline)
    _limit_pipeline_price_context(
        validation_pipeline, pd.Timestamp(x_train.index.max())
    )
    try:
        validation_pipeline.fit(x_train)
    except ValueError as exc:
        if not _pipeline_selected_no_assets(validation_pipeline):
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    n_test_folds = settings.get("n_test_folds", 6)
    cv = CombinatorialPurgedCV(
        n_folds=n_folds,
        n_test_folds=n_test_folds,
    )
    cv_summary = series_to_rows(cv.summary(x_test), "value")
    try:
        population = causal_cpcv_predict(
            strategy.pipeline,
            x_train,
            x_test,
            cv,
            portfolio_params={
                "annualization_factor": annualized_factor(
                    settings.get("interval", "CANDLE_INTERVAL_DAY")
                ),
                "tag": strategy.name,
            },
            n_jobs=int(settings.get("n_jobs", 1)),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    paths = population_to_paths(population)
    unique_path_count = count_unique_paths(paths)
    cv_summary.append(
        {
            "metric": "Number of Unique Chart Paths",
            "value": str(unique_path_count),
            "numeric_value": float(unique_path_count),
        }
    )

    report_rows = population_report_rows(population, paths)

    return {
        "metadata": {
            "model_name": model_name,
            "strategy_name": strategy.name,
            "strategy_description": strategy.description,
            "test_name": settings.get("test_name", ""),
            "test_type": "CPCV",
            "generated_at": datetime.now(UTC).isoformat(),
            "settings": settings,
            "train_period": {
                "start": timestamp_to_string(x_train.index.min()),
                "end": timestamp_to_string(x_train.index.max()),
                "rows": len(x_train),
            },
            "test_period": {
                "start": timestamp_to_string(x_test.index.min()),
                "end": timestamp_to_string(x_test.index.max()),
                "rows": len(x_test),
            },
            "assets": [
                {
                    "figi": item.get("figi"),
                    "ticker": item.get("ticker"),
                    "name": item.get("name"),
                }
                for item in stocks
                if item.get("figi") in set(figis)
            ],
            "asset_count": len(returns.columns),
            "date_policy": {
                "mode": "causal_cpcv",
                "rule": (
                    "Each test segment is fitted only on the base train period and "
                    "CPCV training rows strictly earlier than test_start; long-form "
                    "price context is limited through that fold's train_end."
                ),
            },
        },
        "cv_summary": cv_summary,
        "report": report_rows,
        "paths": paths,
    }


def causal_cpcv_predict(
    pipeline: Any,
    x_train: pd.DataFrame,
    x_test: pd.DataFrame,
    cv: CombinatorialPurgedCV,
    *,
    portfolio_params: dict[str, Any] | None = None,
    n_jobs: int = 1,
) -> Population:
    """Build CPCV paths without training any test segment on later observations."""
    splits = list(cv.split(x_test))
    path_ids = cv.get_path_ids()
    path_count = int(np.max(path_ids)) + 1
    path_portfolios: list[list[Portfolio]] = [[] for _ in range(path_count)]

    work_items = []
    for split_index, (candidate_train, test_segments) in enumerate(splits):
        for segment_index, test_index in enumerate(test_segments):
            if len(test_index) == 0:
                continue
            path_id = int(path_ids[split_index, segment_index])
            work_items.append((path_id, candidate_train, test_index))

    worker_count = resolve_n_jobs(n_jobs)
    if worker_count == 1:
        results = [
            _fit_cpcv_segment(pipeline, x_train, x_test, item) for item in work_items
        ]
    else:
        with ThreadPoolExecutor(
            max_workers=min(worker_count, len(work_items)),
            thread_name_prefix="cpcv",
        ) as executor:
            results = list(
                executor.map(
                    lambda item: _fit_cpcv_segment(pipeline, x_train, x_test, item),
                    work_items,
                )
            )

    for path_id, portfolio in results:
        path_portfolios[path_id].append(portfolio)

    params = {} if portfolio_params is None else portfolio_params.copy()
    name = params.pop("name", "path")
    return Population(
        [
            MultiPeriodPortfolio(
                portfolios=portfolios,
                name=f"{name}_{path_id}",
                check_observations_order=False,
                **params,
            )
            for path_id, portfolios in enumerate(path_portfolios)
        ]
    )


def resolve_n_jobs(n_jobs: int) -> int:
    if n_jobs == -1:
        return max(1, os.cpu_count() or 1)
    if n_jobs < 1:
        raise ValueError("n_jobs must be -1 or a positive integer.")
    return n_jobs


def _fit_cpcv_segment(
    pipeline: Any,
    x_train: pd.DataFrame,
    x_test: pd.DataFrame,
    work_item: tuple[int, np.ndarray, np.ndarray],
) -> tuple[int, Portfolio]:
    path_id, candidate_train, test_index = work_item
    test_start_position = int(test_index[0])
    earlier_train = candidate_train[candidate_train < test_start_position]
    fold_train = pd.concat([x_train, x_test.iloc[earlier_train]])
    test_returns = x_test.iloc[test_index]

    fitted_pipeline = clone(pipeline)
    train_end = pd.Timestamp(fold_train.index.max())
    _limit_pipeline_price_context(fitted_pipeline, train_end)
    try:
        fitted_pipeline.fit(fold_train)
    except ValueError:
        if not _pipeline_selected_no_assets(fitted_pipeline):
            raise
        portfolio = _cash_portfolio(test_returns)
    else:
        portfolio = fitted_pipeline.predict(test_returns)
    return path_id, portfolio


def _pipeline_selected_no_assets(pipeline: Any) -> bool:
    """Return True only when a fitted selector produced an empty asset set."""
    for _, step in getattr(pipeline, "steps", [])[:-1]:
        get_mask = getattr(step, "_get_support_mask", None)
        if not callable(get_mask):
            continue
        try:
            mask = np.asarray(get_mask(), dtype=bool)
        except (AttributeError, TypeError, ValueError):
            continue
        if mask.size > 0 and not mask.any():
            return True
    return False


def _cash_portfolio(test_returns: pd.DataFrame) -> Portfolio:
    """Represent an empty-selection CPCV segment as a fully cash portfolio."""
    return Portfolio(
        X=test_returns,
        weights=np.zeros(test_returns.shape[1], dtype=float),
        name="cash",
    )


def _limit_pipeline_price_context(pipeline: Any, train_end: pd.Timestamp) -> None:
    """Expose long-form candles only through the causal CPCV training end."""
    cutoff = pd.to_datetime(train_end, errors="raise", utc=True).tz_localize(None)
    for _, step in getattr(pipeline, "steps", []):
        prices = getattr(step, "asset_universe_prices", None)
        if not isinstance(prices, pd.DataFrame) or "time" not in prices.columns:
            continue

        limited = prices.copy()
        limited["time"] = pd.to_datetime(
            limited["time"],
            errors="coerce",
            utc=True,
        ).dt.tz_localize(None)
        step.asset_universe_prices = limited.loc[limited["time"] <= cutoff].copy()


def build_returns_matrix(prices: pd.DataFrame) -> pd.DataFrame:
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
        prices.pivot_table(
            index="time",
            columns="ticker",
            values="close",
            aggfunc="last",
        )
        .sort_index()
        .ffill()
        .dropna(axis=1, how="all")
    )
    close = close.loc[:, close.nunique(dropna=True) > 1]
    if close.empty:
        raise HTTPException(
            status_code=422,
            detail="Close price matrix is empty after cleaning.",
        )
    return close.pct_change(fill_method=None).fillna(0)


def load_registered_model(model_name: str) -> type[Strategy]:
    for name in sorted(sys.modules, reverse=True):
        if name == "its.strategies.models" or name.startswith("its.strategies.models."):
            del sys.modules[name]
    module = importlib.import_module("its.strategies.models")
    registered_names = set(getattr(module, "__all__", []))
    if model_name not in registered_names:
        raise HTTPException(status_code=404, detail="Model is not registered.")
    model_cls = getattr(module, model_name, None)
    if model_cls is None:
        raise HTTPException(status_code=404, detail="Model is not available.")
    return model_cls


def combine_population(population: Any) -> Any:
    iterator = iter(population)
    try:
        return next(iterator)
    except StopIteration as exc:
        raise HTTPException(status_code=422, detail="CPCV produced no paths.") from exc


def population_report_rows(
    population: Any,
    paths: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    summaries = population_summary_frame(population)
    rows = [
        {
            "metric": "Number of Test Paths",
            "value": str(len(paths)),
            "numeric_value": float(len(paths)),
        }
    ]

    path_final_returns = pd.Series(
        [
            safe_float(path.get("final_return"))
            for path in paths
            if safe_float(path.get("final_return")) is not None
        ],
        dtype="float64",
    )
    if not path_final_returns.empty:
        rows.extend(
            [
                metric_row("Ann. Ret (Median)", path_final_returns.median()),
                metric_row("Ann. Ret (Mean)", path_final_returns.mean()),
                metric_row(
                    "Ann. Ret (Std)",
                    path_final_returns.std() if len(path_final_returns) > 1 else 0.0,
                ),
            ]
        )

    sharpe_series = first_metric_series(
        summaries,
        "Annualized Sharpe Ratio",
        "Sharpe Ratio",
    )
    if sharpe_series is not None:
        rows.extend(
            [
                metric_row("Sharpe Ratio (Median)", sharpe_series.median()),
                metric_row(
                    "Sharpe Stability (Std)",
                    sharpe_series.std() if len(sharpe_series) > 1 else 0.0,
                ),
            ]
        )

    for metric_name in (
        "Annualized Mean",
        "Mean",
        "Calmar Ratio",
        "MAX Drawdown",
        "Max Drawdown",
        "CVaR at 95%",
        "Annualized Sharpe Ratio",
        "Sharpe Ratio",
        "Value at Risk",
        "VaR at 95%",
        "Average Drawdown",
    ):
        series = first_metric_series(summaries, metric_name)
        if series is None:
            continue
        metric_label = normalize_metric_label(metric_name)
        if any(row["metric"] == f"{metric_label} (Median)" for row in rows):
            continue
        rows.extend(
            [
                metric_row(f"{metric_label} (Median)", series.median()),
                metric_row(
                    f"{metric_label} (Std)",
                    series.std() if len(series) > 1 else 0.0,
                ),
            ]
        )

    return [row for row in rows if row["value"] != ""]


def population_summary_frame(population: Any) -> pd.DataFrame:
    summary_rows: list[dict[str, float]] = []
    for portfolio in population:
        summary = getattr(portfolio, "summary", None)
        if summary is None:
            continue
        if callable(summary):
            summary = summary()
        if not isinstance(summary, pd.Series):
            summary = pd.Series(summary)
        numeric_row = {
            str(index): number
            for index, value in summary.items()
            if (number := safe_float(value)) is not None
        }
        if numeric_row:
            summary_rows.append(numeric_row)
    return pd.DataFrame(summary_rows)


def first_metric_series(
    summaries: pd.DataFrame,
    *metric_names: str,
) -> pd.Series | None:
    if summaries.empty:
        return None
    for metric_name in metric_names:
        if metric_name in summaries.columns:
            series = pd.to_numeric(summaries[metric_name], errors="coerce").dropna()
            if not series.empty:
                return series
    return None


def normalize_metric_label(metric_name: str) -> str:
    return {
        "Annualized Mean": "Annualized Mean",
        "Mean": "Mean",
        "MAX Drawdown": "MAX Drawdown",
        "Max Drawdown": "Max Drawdown",
        "Annualized Sharpe Ratio": "Annualized Sharpe Ratio",
        "Sharpe Ratio": "Sharpe Ratio",
    }.get(metric_name, metric_name)


def metric_row(metric: str, value: Any) -> dict[str, Any]:
    return {
        "metric": metric,
        "value": stringify_value(value),
        "numeric_value": safe_float(value),
    }


def population_to_paths(population: Any) -> list[dict[str, Any]]:
    paths = []
    for index, portfolio in enumerate(population, start=1):
        returns = getattr(portfolio, "cumulative_returns_df", None)
        if returns is None:
            continue
        if callable(returns):
            returns = returns()
        frame = returns.copy()
        if isinstance(frame, pd.Series):
            series = frame
        elif len(frame.columns) == 1:
            series = frame.iloc[:, 0]
        else:
            series = frame.mean(axis=1)

        points = [
            {
                "time": timestamp_to_string(row_index),
                "value": safe_float(value),
            }
            for row_index, value in series.items()
            if safe_float(value) is not None
        ]
        if not points:
            continue
        paths.append(
            {
                "name": getattr(portfolio, "name", None) or f"path_{index}",
                "points": points,
                "final_return": points[-1]["value"],
            }
        )
    return paths


def count_unique_paths(paths: list[dict[str, Any]]) -> int:
    signatures = set()
    for path in paths:
        signatures.add(
            tuple(
                (point["time"], round(point["value"], 12))
                for point in path.get("points", [])
            )
        )
    return len(signatures)


def series_to_rows(series: Any, value_key: str) -> list[dict[str, Any]]:
    if not isinstance(series, pd.Series):
        series = pd.Series(series)
    return [
        {
            "metric": str(index),
            value_key: stringify_value(value),
            "numeric_value": safe_float(value),
        }
        for index, value in series.items()
    ]


def stringify_value(value: Any) -> str:
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return timestamp_to_string(value)
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value)


def safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def timestamp_to_string(value: Any) -> str:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def annualized_factor(interval: str) -> int:
    return {
        "CANDLE_INTERVAL_HOUR": 252 * 7,
        "CANDLE_INTERVAL_DAY": 252,
        "CANDLE_INTERVAL_WEEK": 52,
        "CANDLE_INTERVAL_MONTH": 12,
    }.get(interval, 252)


def list_test_paths(model_name: str) -> list[Path]:
    prefix = f"{safe_name(model_name)}_"
    suffix = "_cpcv.json"
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
        "train_period": metadata.get("train_period", {}),
        "test_period": metadata.get("test_period", {}),
        "asset_count": metadata.get("asset_count", 0),
    }


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=500, detail="Cached CPCV file is invalid."
        ) from exc


def cache_path(model_name: str, test_name: str) -> Path:
    return CACHE_DIR / f"{safe_name(model_name)}_{safe_name(test_name)}_cpcv.json"


def safe_name(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return normalized.strip("._") or "unnamed"
