from __future__ import annotations

import importlib
import json
import math
import os
import re
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from skfolio.model_selection import CombinatorialPurgedCV, cross_val_predict


DATA_BACKEND_BASE_URL = os.getenv(
    "DATA_BACKEND_BASE_URL",
    "http://data-backend:8000/api/v1",
).rstrip("/")
CACHE_DIR = Path(
    os.getenv("STRATEGY_TEST_CACHE_DIR", "/app/its/data/strategy_tests/cpcv")
)
DEFAULT_ASSET_LIMIT = 40

router = APIRouter(prefix="/models/{model_name}/cpcv", tags=["cpcv"])


class CpcvRunRequest(BaseModel):
    test_name: str = Field(min_length=1, max_length=80)
    start_date: date
    end_date: date
    interval: str = "CANDLE_INTERVAL_DAY"
    class_code: str = "TQBR"
    n_folds: int = Field(default=10, ge=2, le=30)
    n_test_folds: int = Field(default=6, ge=1, le=29)
    asset_limit: int = Field(default=DEFAULT_ASSET_LIMIT, ge=2, le=500)
    force: bool = False


@router.get("/tests")
async def list_cpcv_tests(model_name: str) -> dict[str, Any]:
    return {"items": [read_test_summary(path) for path in list_test_paths(model_name)]}


@router.get("/tests/{test_name}")
async def get_cpcv_test(model_name: str, test_name: str) -> dict[str, Any]:
    path = cache_path(model_name, test_name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="CPCV test cache was not found.")
    return read_json(path)


@router.post("/run")
async def run_cpcv_test(model_name: str, request: CpcvRunRequest) -> dict[str, Any]:
    if request.n_test_folds >= request.n_folds:
        raise HTTPException(
            status_code=422,
            detail="n_test_folds must be lower than n_folds.",
        )
    if request.start_date >= request.end_date:
        raise HTTPException(
            status_code=422,
            detail="start_date must be before end_date.",
        )

    path = cache_path(model_name, request.test_name)
    if path.exists() and not request.force:
        return read_json(path)

    result = await build_cpcv_report(model_name, request)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


async def build_cpcv_report(
    model_name: str,
    request: CpcvRunRequest,
) -> dict[str, Any]:
    model_cls = load_registered_model(model_name)
    stocks = await fetch_stocks(request)
    figis = [item["figi"] for item in stocks if item.get("figi")]
    if not figis:
        raise HTTPException(status_code=404, detail="No assets found for CPCV.")

    prices = await fetch_prices(figis, request)
    if prices.empty:
        raise HTTPException(status_code=404, detail="No prices found for CPCV.")

    returns = build_returns_matrix(prices)
    if len(returns) < request.n_folds + 2:
        raise HTTPException(
            status_code=422,
            detail="Not enough price rows for selected CPCV settings.",
        )

    split_index = max(1, int(len(returns) * 0.67))
    if len(returns) - split_index < request.n_folds:
        split_index = len(returns) - request.n_folds
    if split_index <= 0:
        raise HTTPException(
            status_code=422,
            detail="Not enough rows to build train/test split.",
        )

    x_train = returns.iloc[:split_index]
    x_test = returns.iloc[split_index:]

    strategy = model_cls(prices).build()
    strategy.pipeline.fit(x_train)

    cv = CombinatorialPurgedCV(
        n_folds=request.n_folds,
        n_test_folds=request.n_test_folds,
    )
    cv_summary = series_to_rows(cv.summary(x_test), "value")
    population = cross_val_predict(
        strategy.pipeline,
        x_test,
        cv=cv,
        n_jobs=1,
        portfolio_params={
            "annualized_factor": annualized_factor(request.interval),
            "tag": strategy.name,
        },
    )

    report_portfolio = combine_population(population)
    report_rows = series_to_rows(report_portfolio.summary(), "value")

    return {
        "metadata": {
            "model_name": model_name,
            "strategy_name": strategy.name,
            "strategy_description": strategy.description,
            "test_name": request.test_name,
            "test_type": "CPCV",
            "generated_at": datetime.now(UTC).isoformat(),
            "source": DATA_BACKEND_BASE_URL,
            "settings": request.model_dump(mode="json"),
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
        },
        "cv_summary": cv_summary,
        "report": report_rows,
        "paths": population_to_paths(population),
    }


async def fetch_stocks(request: CpcvRunRequest) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.get(
            f"{DATA_BACKEND_BASE_URL}/stocks",
            params={
                "class_code": request.class_code,
                "limit": request.asset_limit,
            },
        )
    payload = handle_data_response(response)
    return payload.get("items", [])


async def fetch_prices(
    figis: list[str],
    request: CpcvRunRequest,
) -> pd.DataFrame:
    params: list[tuple[str, str]] = [
        ("figis", figi) for figi in figis
    ] + [
        ("class_code", request.class_code),
        ("start_date", request.start_date.isoformat()),
        ("end_date", request.end_date.isoformat()),
        ("interval", request.interval),
        ("is_complete", "true"),
    ]
    async with httpx.AsyncClient(timeout=300) as client:
        response = await client.get(f"{DATA_BACKEND_BASE_URL}/prices", params=params)
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


def load_registered_model(model_name: str) -> Any:
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
        combined = next(iterator)
    except StopIteration as exc:
        raise HTTPException(status_code=422, detail="CPCV produced no paths.") from exc
    for portfolio in iterator:
        combined += portfolio
    return combined


def population_to_paths(population: Any) -> list[dict[str, Any]]:
    paths = []
    for index, portfolio in enumerate(population, start=1):
        returns = getattr(portfolio, "cumulative_returns_df", None)
        if returns is None:
            continue
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
                "name": f"path_{index}",
                "points": points,
                "final_return": points[-1]["value"],
            }
        )
    return paths


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
        path
        for path in CACHE_DIR.glob(f"{prefix}*{suffix}")
        if path.is_file()
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
        raise HTTPException(status_code=500, detail="Cached CPCV file is invalid.") from exc


def cache_path(model_name: str, test_name: str) -> Path:
    return CACHE_DIR / f"{safe_name(model_name)}_{safe_name(test_name)}_cpcv.json"


def safe_name(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return normalized.strip("._") or "unnamed"
