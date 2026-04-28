from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import HTTPException
from skfolio.model_selection import WalkForward, cross_val_predict

from its.strategies.testing.cpcv import (
    annualized_factor,
    build_returns_matrix,
    load_registered_model,
    population_to_paths,
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

    strategy = model_cls(prices).build()
    strategy.pipeline.fit(x_train)

    train_size_months = settings.get("train_size_months", 3)
    freq_months = settings.get("freq_months", 3)
    walk_forward = WalkForward(
        test_size=settings.get("wf_test_size", 1),
        train_size=pd.DateOffset(months=train_size_months),
        freq=pd.DateOffset(months=freq_months),
    )
    windows = describe_walk_forward_windows(walk_forward, x_test)
    population = cross_val_predict(
        strategy.pipeline,
        x_test,
        cv=walk_forward,
        n_jobs=1,
        portfolio_params={
            "annualized_factor": annualized_factor(
                settings.get("interval", "CANDLE_INTERVAL_DAY")
            ),
            "tag": strategy.name,
        },
    )
    oos_curve = build_stitched_oos_curve(population)

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
        "paths": population_to_paths(population),
    }


def walk_forward_summary(population: Any, settings: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"metric": "Number of WF Windows", "value": str(len(population)), "numeric_value": float(len(population))},
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


def build_stitched_oos_curve(population: Any) -> dict[str, Any]:
    returns_parts = []
    for window_index, portfolio in enumerate(population):
        returns = getattr(portfolio, "returns_df", None)
        if returns is None:
            continue
        if callable(returns):
            returns = returns()
        if not isinstance(returns, pd.Series):
            returns = pd.Series(returns)
        returns = returns.copy()
        returns.index = pd.to_datetime(returns.index, errors="coerce")
        returns = returns.loc[returns.index.notna()].sort_index()
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


def describe_walk_forward_windows(
    walk_forward: WalkForward,
    x_test: pd.DataFrame,
) -> list[dict[str, Any]]:
    windows = []
    for split_id, (train_index, test_index) in enumerate(walk_forward.split(x_test), start=1):
        train_dates = x_test.index[train_index]
        test_dates = x_test.index[test_index]
        windows.append(
            {
                "split_id": split_id,
                "train_start": timestamp_to_string(train_dates.min()),
                "train_end": timestamp_to_string(train_dates.max()),
                "train_rows": len(train_dates),
                "test_start": timestamp_to_string(test_dates.min()),
                "test_end": timestamp_to_string(test_dates.max()),
                "test_rows": len(test_dates),
            }
        )
    return windows


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
    return CACHE_DIR / f"{safe_name(model_name)}_{safe_name(test_name)}_walk_forward.json"
