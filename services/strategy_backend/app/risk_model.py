from __future__ import annotations

import json
import os
from datetime import date
from typing import Any, Literal

import httpx
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from its.authz.context import AuthContext
from its.authz.dependencies import require_permissions
from its.authz.permissions import Permissions
from its.strategies.testing.risk_model import (
    cache_path,
    generate_risk_model_report,
    list_risk_models,
    list_test_paths,
    read_json,
    read_test_summary,
    risk_model_definition,
)

DATA_BACKEND_BASE_URL = os.getenv(
    "DATA_BACKEND_BASE_URL",
    "http://data-backend:8000/api/v1",
).rstrip("/")

SimulationMethod = Literal["historical_bootstrap", "multivariate_normal"]

router = APIRouter(prefix="/models/{model_name}/risk-models", tags=["risk-models"])


class RiskModelRunRequest(BaseModel):
    test_name: str = Field(min_length=1, max_length=80)
    start_date: date
    end_date: date
    interval: str = "CANDLE_INTERVAL_DAY"
    class_code: str = "TQBR"
    test_size: float = Field(default=0.33, ge=0.05, le=0.80)
    portfolio_value: float = Field(default=1_000_000.0, gt=0)
    confidence_level: float = Field(default=0.95, gt=0.5, lt=1)
    horizon_days: int = Field(default=1, ge=1, le=252)
    n_simulations: int = Field(default=50_000, ge=100, le=1_000_000)
    simulation_method: SimulationMethod = "historical_bootstrap"
    random_state: int = 42
    n_buckets: int = Field(default=64, ge=8, le=1024)
    qae_iterations: int = Field(default=12, ge=1, le=64)
    qae_shots: int = Field(default=2_000, ge=100, le=1_000_000)


@router.get("/available")
async def available_risk_models(
    _auth: AuthContext = Depends(require_permissions(Permissions.STRATEGY_TEST_READ)),
) -> dict[str, Any]:
    return {"items": list_risk_models()}


@router.get("/{risk_model}/tests")
async def list_risk_model_tests(
    model_name: str,
    risk_model: str,
    _auth: AuthContext = Depends(require_permissions(Permissions.STRATEGY_TEST_READ)),
) -> dict[str, Any]:
    risk_model = normalize_risk_model(risk_model)
    risk_model_definition(risk_model)
    return {
        "items": [
            read_test_summary(path) for path in list_test_paths(model_name, risk_model)
        ]
    }


@router.get("/{risk_model}/tests/{test_name}")
async def get_risk_model_test(
    model_name: str,
    risk_model: str,
    test_name: str,
    _auth: AuthContext = Depends(require_permissions(Permissions.STRATEGY_TEST_READ)),
) -> dict[str, Any]:
    risk_model = normalize_risk_model(risk_model)
    risk_model_definition(risk_model)
    path = cache_path(model_name, risk_model, test_name)
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="Risk Model cache was not found.",
        )
    return read_json(path)


@router.post("/{risk_model}/run")
async def run_risk_model_test(
    model_name: str,
    risk_model: str,
    request: RiskModelRunRequest,
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
    risk_model = normalize_risk_model(risk_model)
    risk_model_definition(risk_model)
    if request.start_date >= request.end_date:
        raise HTTPException(
            status_code=422,
            detail="start_date must be before end_date.",
        )

    authorization = http_request.headers.get("authorization")
    stocks = await fetch_stocks(request, authorization=authorization)
    figis = [item["figi"] for item in stocks if item.get("figi")]
    if not figis:
        raise HTTPException(status_code=404, detail="No assets found for Risk Models.")

    prices = await fetch_prices(figis, request, authorization=authorization)
    if prices.empty:
        raise HTTPException(status_code=404, detail="No prices found for Risk Models.")
    dividends_info = await fetch_dividends(figis, request, authorization=authorization)

    settings = request.model_dump(mode="json")
    settings["risk_model"] = risk_model
    result = generate_risk_model_report(
        model_name,
        risk_model,
        stocks,
        prices,
        settings,
        dividends_info=dividends_info,
    )

    path = cache_path(model_name, risk_model, request.test_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


async def fetch_stocks(
    request: RiskModelRunRequest, *, authorization: str | None
) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=None) as client:
        response = await client.get(
            f"{DATA_BACKEND_BASE_URL}/stocks",
            params={"class_code": request.class_code},
            headers=auth_headers(authorization),
        )
    payload = handle_data_response(response)
    return payload.get("items", [])


async def fetch_prices(
    figis: list[str],
    request: RiskModelRunRequest,
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
    async with httpx.AsyncClient(timeout=None) as client:
        response = await client.get(
            f"{DATA_BACKEND_BASE_URL}/prices",
            params=params,
            headers=auth_headers(authorization),
        )
    payload = handle_data_response(response)
    return pd.DataFrame(payload.get("items", []))


async def fetch_dividends(
    figis: list[str],
    request: RiskModelRunRequest,
    *,
    authorization: str | None,
) -> pd.DataFrame:
    params: list[tuple[str, str]] = [("figis", figi) for figi in figis] + [
        ("class_code", request.class_code),
        ("end_date", request.end_date.isoformat()),
    ]
    async with httpx.AsyncClient(timeout=None) as client:
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


def normalize_risk_model(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_")
    return risk_model_definition(normalized)["id"]
