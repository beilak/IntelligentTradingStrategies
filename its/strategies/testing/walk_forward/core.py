from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from fastapi import HTTPException
from skfolio.model_selection import WalkForward
from skfolio.portfolio import MultiPeriodPortfolio, Portfolio
from sklearn.base import clone

from its.strategies.testing.cpcv import (
    annualized_factor,
    build_returns_matrix,
    load_registered_model,
    safe_float,
    safe_name,
    series_to_rows,
    timestamp_to_string,
)

CACHE_DIR = Path(
    os.getenv("STRATEGY_WF_CACHE_DIR", "/app/its/data/strategy_tests/walk_forward")
)


def generate_walk_forward_report(
    model_name: str,
    stocks: list[dict[str, Any]],
    prices: pd.DataFrame,
    settings: dict[str, Any],
    dividends_info: pd.DataFrame | None = None,
) -> dict[str, Any]:
    model_cls = load_registered_model(model_name)
    figis = [item["figi"] for item in stocks if item.get("figi")]
    if not figis:
        raise HTTPException(status_code=404, detail="No assets found for WalkForward.")
    if prices.empty:
        raise HTTPException(status_code=404, detail="No prices found for WalkForward.")

    returns = build_returns_matrix(prices)
    test_size_fraction = settings.get("test_size", 0.33)
    split_index = max(1, int(len(returns) * (1 - test_size_fraction)))
    if split_index >= len(returns) - 1:
        split_index = max(1, len(returns) - 2)
    if split_index <= 0:
        raise HTTPException(
            status_code=422,
            detail="Not enough rows to build train/test split.",
        )

    x_train = returns.iloc[:split_index]
    x_test = returns.iloc[split_index:].copy()
    x_test.index = pd.to_datetime(x_test.index)

    if len(x_test) < 2:
        raise HTTPException(
            status_code=422,
            detail="Not enough test rows for WalkForward.",
        )

    strategy = model_cls(
        prices,
        pd.DataFrame(stocks),
        _dividends_info=dividends_info,
    ).build()

    train_size_months = settings.get("train_size_months", 3)
    freq_months = settings.get("freq_months", 3)
    walk_forward = WalkForward(
        test_size=settings.get("wf_test_size", 1),
        train_size=pd.DateOffset(months=train_size_months),
        freq=pd.DateOffset(months=freq_months),
    )
    splits = collect_walk_forward_splits(walk_forward, x_test)
    windows = splits_to_windows(splits)
    if not windows:
        test_period_start = timestamp_to_string(x_test.index.min())
        test_period_end = timestamp_to_string(x_test.index.max())
        raise HTTPException(
            status_code=422,
            detail=(
                "WalkForward produced no test windows for the selected settings. "
                f"OOS period is {test_period_start} -> {test_period_end} "
                f"({len(x_test)} rows) after applying test_size={test_size_fraction}. "
                f"Requested train_size_months={train_size_months}, "
                f"freq_months={freq_months}, wf_test_size={settings.get('wf_test_size', 1)}."
            ),
        )
    population = walk_forward_cross_val_predict(
        strategy.pipeline,
        x_test,
        splits,
        portfolio_params={
            "annualized_factor": annualized_factor(
                settings.get("interval", "CANDLE_INTERVAL_DAY")
            ),
            "tag": strategy.name,
        },
    )
    paths = population_to_dated_paths(population, splits)
    oos_curve = build_stitched_oos_curve(population, splits)

    return {
        "metadata": {
            "model_name": model_name,
            "strategy_name": strategy.name,
            "strategy_description": strategy.description,
            "test_name": settings.get("test_name", ""),
            "test_type": "WalkForward",
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
            "stitch_rule": oos_curve["stitch_rule"],
        },
        "cv_summary": walk_forward_summary(population, settings),
        "report": series_to_rows(population.summary(), "value"),
        "oos_curve": oos_curve,
        "windows": windows,
        "paths": paths,
    }


def walk_forward_cross_val_predict(
    pipeline: Any,
    X: pd.DataFrame,
    splits: list[dict[str, Any]],
    *,
    portfolio_params: dict[str, Any] | None = None,
) -> MultiPeriodPortfolio:
    """Fit and predict every WF fold with point-in-time price context.

    ``skfolio.cross_val_predict`` slices ``X`` for each fold, but it cannot slice
    long-form candle data stored as estimator parameters.  Strategies using that
    context would therefore see candles after the fold's training end.  Clone the
    pipeline per fold and explicitly limit its context before fitting.
    """
    portfolios = []
    for split in splits:
        train_dates = pd.DatetimeIndex(split["train_dates"])
        test_dates = pd.DatetimeIndex(split["test_dates"])
        if train_dates.empty or test_dates.empty:
            continue

        fitted_pipeline = clone(pipeline)
        train_end = pd.Timestamp(train_dates.max())
        _limit_pipeline_price_context(fitted_pipeline, train_end)
        test_returns = X.loc[test_dates]
        try:
            fitted_pipeline.fit(X.loc[train_dates])
        except ValueError:
            if not _pipeline_selected_no_assets(fitted_pipeline):
                raise
            portfolios.append(_cash_portfolio(test_returns))
            continue
        portfolios.append(fitted_pipeline.predict(test_returns))

    params = {} if portfolio_params is None else portfolio_params.copy()
    return MultiPeriodPortfolio(
        portfolios=portfolios,
        check_observations_order=False,
        **params,
    )


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
    """Represent an empty-selection WF fold as a fully cash portfolio."""
    return Portfolio(
        X=test_returns,
        weights=np.zeros(test_returns.shape[1], dtype=float),
        name="cash",
    )


def _limit_pipeline_price_context(pipeline: Any, train_end: pd.Timestamp) -> None:
    """Expose long-form candles only through the current WF training end."""
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


def walk_forward_summary(
    population: Any, settings: dict[str, Any]
) -> list[dict[str, Any]]:
    return [
        {
            "metric": "Number of WF Windows",
            "value": str(len(population)),
            "numeric_value": float(len(population)),
        },
        {
            "metric": "Train Size Months",
            "value": str(settings.get("train_size_months", 3)),
            "numeric_value": float(settings.get("train_size_months", 3)),
        },
        {
            "metric": "Frequency Months",
            "value": str(settings.get("freq_months", 3)),
            "numeric_value": float(settings.get("freq_months", 3)),
        },
        {
            "metric": "WalkForward Test Size",
            "value": str(settings.get("wf_test_size", 1)),
            "numeric_value": float(settings.get("wf_test_size", 1)),
        },
    ]


def build_stitched_oos_curve(
    population: Any,
    splits: list[dict[str, Any]],
) -> dict[str, Any]:
    returns_parts = []
    for window_index, (portfolio, split) in enumerate(
        zip(population, splits, strict=False)
    ):
        returns = extract_portfolio_series(
            portfolio,
            "returns_df",
            split["test_dates"],
        )
        if returns.empty:
            continue
        frame = returns.to_frame("return")
        frame["window_index"] = window_index
        returns_parts.append(frame)

    if not returns_parts:
        return {
            "name": "WalkForward OOS Backtest",
            "stitch_rule": "No OOS returns were available.",
            "points": [],
            "final_return": None,
            "rows": 0,
            "duplicates_removed": 0,
        }

    stitched = pd.concat(returns_parts).sort_values(["window_index"])
    duplicate_count = int(stitched.index.duplicated(keep="first").sum())
    stitched = stitched.loc[~stitched.index.duplicated(keep="first")]
    stitched = stitched.sort_index()
    cumulative_returns = (1 + stitched["return"].fillna(0)).cumprod() - 1
    stitched["cumulative_return"] = cumulative_returns
    points = [
        {
            "time": timestamp_to_string(index),
            "value": float(value),
        }
        for index, value in cumulative_returns.items()
    ]
    segments = build_oos_segments(stitched)
    return {
        "name": "WalkForward OOS Backtest",
        "stitch_rule": (
            "OOS returns are concatenated by WF window order; duplicate dates keep "
            "the first window value and later duplicates are dropped."
        ),
        "points": points,
        "segments": segments,
        "final_return": points[-1]["value"] if points else None,
        "rows": len(points),
        "duplicates_removed": duplicate_count,
    }


def build_oos_segments(stitched: pd.DataFrame) -> list[dict[str, Any]]:
    segments = []
    previous_last_point: dict[str, Any] | None = None
    for window_index, window_frame in stitched.groupby("window_index", sort=True):
        window_frame = window_frame.sort_index()
        points = [
            {
                "time": timestamp_to_string(index),
                "value": float(row["cumulative_return"]),
            }
            for index, row in window_frame.iterrows()
        ]
        if not points:
            continue
        if previous_last_point is not None:
            points = [previous_last_point, *points]
        segments.append(
            {
                "name": f"WF window {int(window_index) + 1}",
                "window_index": int(window_index),
                "points": points,
                "final_return": points[-1]["value"],
            }
        )
        previous_last_point = points[-1]
    return segments


def collect_walk_forward_splits(
    walk_forward: WalkForward,
    x_test: pd.DataFrame,
) -> list[dict[str, Any]]:
    splits = []
    for split_id, (train_index, test_index) in enumerate(
        walk_forward.split(x_test), start=1
    ):
        train_dates = x_test.index[train_index]
        test_dates = x_test.index[test_index]
        splits.append(
            {
                "split_id": split_id,
                "train_dates": train_dates,
                "test_dates": test_dates,
            }
        )
    return splits


def splits_to_windows(splits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    windows = []
    for split in splits:
        train_dates = split["train_dates"]
        test_dates = split["test_dates"]
        windows.append(
            {
                "split_id": split["split_id"],
                "train_start": timestamp_to_string(train_dates.min()),
                "train_end": timestamp_to_string(train_dates.max()),
                "train_rows": len(train_dates),
                "test_start": timestamp_to_string(test_dates.min()),
                "test_end": timestamp_to_string(test_dates.max()),
                "test_rows": len(test_dates),
            }
        )
    return windows


def population_to_dated_paths(
    population: Any,
    splits: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    windows = []
    for index, (portfolio, split) in enumerate(
        zip(population, splits, strict=False), start=1
    ):
        returns = extract_portfolio_series(
            portfolio,
            "cumulative_returns_df",
            split["test_dates"],
        )
        if returns.empty:
            continue
        points = [
            {
                "time": timestamp_to_string(row_index),
                "value": float(value),
            }
            for row_index, value in returns.items()
            if safe_float(value) is not None
        ]
        if not points:
            continue
        windows.append(
            {
                "name": getattr(portfolio, "name", None) or f"wf_window_{index}",
                "final_return": points[-1]["value"],
                "points": points,
            }
        )
    return windows


def extract_portfolio_series(
    portfolio: Any,
    attribute_name: str,
    target_dates: pd.Index,
) -> pd.Series:
    values = getattr(portfolio, attribute_name, None)
    if values is None:
        return pd.Series(dtype="float64")
    if callable(values):
        values = values()
    if isinstance(values, pd.DataFrame):
        if values.empty:
            return pd.Series(dtype="float64")
        if len(values.columns) == 1:
            series = values.iloc[:, 0]
        else:
            series = values.mean(axis=1)
    elif isinstance(values, pd.Series):
        series = values
    else:
        series = pd.Series(values)

    series = pd.to_numeric(series, errors="coerce").dropna()
    if series.empty:
        return pd.Series(dtype="float64")

    target_dates = pd.to_datetime(pd.Index(target_dates), errors="coerce")
    target_dates = target_dates[target_dates.notna()]
    if len(target_dates) == 0:
        return pd.Series(dtype="float64")

    if len(series) != len(target_dates):
        if len(series) > len(target_dates):
            series = series.iloc[-len(target_dates) :]
        else:
            target_dates = target_dates[-len(series) :]

    series = series.copy()
    series.index = pd.Index(target_dates)
    return series.sort_index()


def list_test_paths(model_name: str) -> list[Path]:
    prefix = f"{safe_name(model_name)}_"
    suffix = "_walk_forward.json"
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
            status_code=500, detail="Cached WalkForward file is invalid."
        ) from exc


def cache_path(model_name: str, test_name: str) -> Path:
    return (
        CACHE_DIR / f"{safe_name(model_name)}_{safe_name(test_name)}_walk_forward.json"
    )
