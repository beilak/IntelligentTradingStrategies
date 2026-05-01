from __future__ import annotations

import json
import os
from datetime import date
from typing import Any

import httpx
import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from its.strategies.testing.walk_forward import (
    cache_path,
    generate_walk_forward_report,
    list_test_paths,
    read_json,
    read_test_summary,
)

DATA_BACKEND_BASE_URL = os.getenv(
    "DATA_BACKEND_BASE_URL",
    "http://data-backend:8000/api/v1",
).rstrip("/")

router = APIRouter(prefix="/models/{model_name}/walk-forward", tags=["walk-forward"])


class WalkForwardRunRequest(BaseModel):
    test_name: str = Field(min_length=1, max_length=80)
    start_date: date
    end_date: date
    interval: str = "CANDLE_INTERVAL_DAY"
    class_code: str = "TQBR"
    test_size: float = Field(default=0.33, ge=0.05, le=0.80)
    train_size_months: int = Field(default=3, ge=1, le=120)
    freq_months: int = Field(default=3, ge=1, le=120)
    wf_test_size: int = Field(default=1, ge=1, le=500)


@router.get("/tests")
async def list_walk_forward_tests(model_name: str) -> dict[str, Any]:
    return {"items": [read_test_summary(path) for path in list_test_paths(model_name)]}


@router.get("/tests/{test_name}")
async def get_walk_forward_test(model_name: str, test_name: str) -> dict[str, Any]:
    path = cache_path(model_name, test_name)
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="WalkForward test cache was not found.",
        )
    return read_json(path)


@router.post("/run")
async def run_walk_forward_test(
    model_name: str,
    request: WalkForwardRunRequest,
) -> dict[str, Any]:
    if request.start_date >= request.end_date:
        raise HTTPException(
            status_code=422,
            detail="start_date must be before end_date.",
        )

    path = cache_path(model_name, request.test_name)
    stocks = await fetch_stocks(request)
    figis = [item["figi"] for item in stocks if item.get("figi")]
    if not figis:
        raise HTTPException(status_code=404, detail="No assets found for WalkForward.")

    prices = await fetch_prices(figis, request)
    if prices.empty:
        raise HTTPException(status_code=404, detail="No prices found for WalkForward.")
    dividends_info = await fetch_dividends(figis, request)

    settings = request.model_dump(mode="json")
    result = generate_walk_forward_report(
        model_name,
        stocks,
        prices,
        settings,
        dividends_info=dividends_info,
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


async def fetch_stocks(request: WalkForwardRunRequest) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.get(
            f"{DATA_BACKEND_BASE_URL}/stocks",
            params={
                "class_code": request.class_code,
            },
        )
    payload = handle_data_response(response)
    return payload.get("items", [])


async def fetch_prices(
    figis: list[str],
    request: WalkForwardRunRequest,
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


async def fetch_dividends(
    figis: list[str],
    request: WalkForwardRunRequest,
) -> pd.DataFrame:
    params: list[tuple[str, str]] = [("figis", figi) for figi in figis] + [
        ("class_code", request.class_code),
        ("end_date", request.end_date.isoformat()),
    ]
    async with httpx.AsyncClient(timeout=300) as client:
        response = await client.get(f"{DATA_BACKEND_BASE_URL}/dividends", params=params)
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
