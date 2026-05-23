from __future__ import annotations

import json
import os
from datetime import date
from typing import Any

import httpx
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from its.authz.context import AuthContext
from its.authz.dependencies import require_permissions
from its.authz.permissions import Permissions
from its.strategies.testing.cpcv import (
    cache_path,
    generate_cpcv_report,
    list_test_paths,
    read_json,
    read_test_summary,
)

DATA_BACKEND_BASE_URL = os.getenv(
    "DATA_BACKEND_BASE_URL",
    "http://data-backend:8000/api/v1",
).rstrip("/")

router = APIRouter(prefix="/models/{model_name}/cpcv", tags=["cpcv"])


class CpcvRunRequest(BaseModel):
    test_name: str = Field(min_length=1, max_length=80)
    start_date: date
    end_date: date
    interval: str = "CANDLE_INTERVAL_DAY"
    class_code: str = "TQBR"
    n_folds: int = Field(default=10, ge=2, le=30)
    n_test_folds: int = Field(default=6, ge=1, le=29)


@router.get("/tests")
async def list_cpcv_tests(
    model_name: str,
    _auth: AuthContext = Depends(require_permissions(Permissions.STRATEGY_TEST_READ)),
) -> dict[str, Any]:
    return {"items": [read_test_summary(path) for path in list_test_paths(model_name)]}


@router.get("/tests/{test_name}")
async def get_cpcv_test(
    model_name: str,
    test_name: str,
    _auth: AuthContext = Depends(require_permissions(Permissions.STRATEGY_TEST_READ)),
) -> dict[str, Any]:
    path = cache_path(model_name, test_name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="CPCV test cache was not found.")
    return read_json(path)


@router.post("/run")
async def run_cpcv_test(
    model_name: str,
    request: CpcvRunRequest,
    http_request: Request,
    _auth: AuthContext = Depends(
        require_permissions(
            Permissions.STRATEGY_TEST_RUN,
            Permissions.DATA_INSTRUMENTS_READ,
            Permissions.DATA_PRICES_READ,
            Permissions.DATA_DIVIDENDS_READ,
        )
    ),
) -> dict[str, Any]:
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
    authorization = http_request.headers.get("authorization")
    stocks = await fetch_stocks(request, authorization=authorization)
    figis = [item["figi"] for item in stocks if item.get("figi")]
    if not figis:
        raise HTTPException(status_code=404, detail="No assets found for CPCV.")

    prices = await fetch_prices(figis, request, authorization=authorization)
    if prices.empty:
        raise HTTPException(status_code=404, detail="No prices found for CPCV.")
    dividends_info = await fetch_dividends(figis, request, authorization=authorization)

    settings = request.model_dump(mode="json")
    result = generate_cpcv_report(
        model_name,
        stocks,
        prices,
        settings,
        dividends_info=dividends_info,
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


async def fetch_stocks(
    request: CpcvRunRequest, *, authorization: str | None
) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.get(
            f"{DATA_BACKEND_BASE_URL}/stocks",
            params={
                "class_code": request.class_code,
            },
            headers=auth_headers(authorization),
        )
    payload = handle_data_response(response)
    return payload.get("items", [])


async def fetch_prices(
    figis: list[str],
    request: CpcvRunRequest,
    *,
    authorization: str | None,
) -> pd.DataFrame:
    params: list[tuple[str, str]] = [("figis", figi) for figi in figis] + [
        ("class_code", request.class_code),
        ("start_date", request.start_date.isoformat()),
        ("end_date", request.end_date.isoformat()),
        ("interval", request.interval),
        ("is_complete", "true"),
    ]
    async with httpx.AsyncClient(timeout=300) as client:
        response = await client.get(
            f"{DATA_BACKEND_BASE_URL}/prices",
            params=params,
            headers=auth_headers(authorization),
        )
    payload = handle_data_response(response)
    return pd.DataFrame(payload.get("items", []))


async def fetch_dividends(
    figis: list[str],
    request: CpcvRunRequest,
    *,
    authorization: str | None,
) -> pd.DataFrame:
    params: list[tuple[str, str]] = [("figis", figi) for figi in figis] + [
        ("class_code", request.class_code),
        ("end_date", request.end_date.isoformat()),
    ]
    async with httpx.AsyncClient(timeout=300) as client:
        response = await client.get(
            f"{DATA_BACKEND_BASE_URL}/dividends",
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
