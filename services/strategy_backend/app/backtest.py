from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from its.strategies.testing.backtest import (
    cache_path,
    enrich_backtest_payload_with_stocks,
    generate_backtest_report,
    list_test_paths,
    read_json,
    read_test_summary,
)

DATA_BACKEND_BASE_URL = os.getenv(
    "DATA_BACKEND_BASE_URL",
    "http://data-backend:8000/api/v1",
).rstrip("/")

router = APIRouter(prefix="/models/{model_name}/backtest", tags=["backtest"])


class BacktestRunRequest(BaseModel):
    test_name: str = Field(min_length=1, max_length=80)
    start_date: date
    end_date: date
    interval: str = "CANDLE_INTERVAL_DAY"
    class_code: str = "TQBR"
    trading_start_date: date | None = None
    rebalance_freq: str = "3ME"
    rebalance_on: str = "last"
    init_cash: float = Field(default=1_000_000.0, gt=0)
    fees: float = Field(default=0.0008, ge=0)
    slippage: float = Field(default=0.0, ge=0)
    freq: str = "1D"
    rolling_window: int = Field(default=252, ge=2, le=2000)
    tax_rate: float = Field(default=0.13, ge=0, le=1)


@router.get("/tests")
async def list_backtest_tests(model_name: str) -> dict[str, Any]:
    return {"items": [read_test_summary(path) for path in list_test_paths(model_name)]}


@router.get("/tests/{test_name}")
async def get_backtest_test(model_name: str, test_name: str) -> dict[str, Any]:
    path = cache_path(model_name, test_name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Backtest cache was not found.")
    return await enrich_cached_backtest(read_json(path))


@router.post("/run")
async def run_backtest_test(
    model_name: str,
    request: BacktestRunRequest,
) -> dict[str, Any]:
    return await run_backtest_flow(
        subject_name=model_name,
        request=request,
        output_path=cache_path(model_name, request.test_name),
        report_factory=generate_backtest_report,
    )


async def run_backtest_flow(
    *,
    subject_name: str,
    request: BacktestRunRequest,
    output_path: Path,
    report_factory: Any,
) -> dict[str, Any]:
    if request.start_date >= request.end_date:
        raise HTTPException(
            status_code=422,
            detail="start_date must be before end_date.",
        )
    if request.trading_start_date and request.trading_start_date < request.start_date:
        raise HTTPException(
            status_code=422,
            detail="trading_start_date must be inside the loaded date range.",
        )

    stocks = await fetch_stocks(request)
    figis = [item["figi"] for item in stocks if item.get("figi")]
    if not figis:
        raise HTTPException(status_code=404, detail="No assets found for Backtesting.")

    prices = await fetch_prices(figis, request)
    if prices.empty:
        raise HTTPException(status_code=404, detail="No prices found for Backtesting.")

    settings = request.model_dump(mode="json")
    if settings.get("trading_start_date") is None:
        settings["trading_start_date"] = settings["start_date"]
    result = report_factory(subject_name, stocks, prices, settings)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


async def fetch_stocks(request: BacktestRunRequest) -> list[dict[str, Any]]:
    return await fetch_stocks_by_class_code(request.class_code)


async def fetch_stocks_by_class_code(class_code: str) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.get(
            f"{DATA_BACKEND_BASE_URL}/stocks",
            params={"class_code": class_code},
        )
    payload = handle_data_response(response)
    return payload.get("items", [])


async def enrich_cached_backtest(payload: dict[str, Any]) -> dict[str, Any]:
    if backtest_payload_has_sectors(payload):
        return payload

    class_code = (
        payload.get("metadata", {})
        .get("settings", {})
        .get("class_code", "TQBR")
    )
    stocks = await fetch_stocks_by_class_code(str(class_code))
    return enrich_backtest_payload_with_stocks(payload, stocks)


def backtest_payload_has_sectors(payload: dict[str, Any]) -> bool:
    for record in payload.get("rebalance_weights", []):
        for weight in record.get("weights", []):
            if weight.get("sector"):
                return True
    return False


async def fetch_prices(
    figis: list[str],
    request: BacktestRunRequest,
) -> pd.DataFrame:
    params: list[tuple[str, str]] = [("figis", figi) for figi in figis] + [
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
