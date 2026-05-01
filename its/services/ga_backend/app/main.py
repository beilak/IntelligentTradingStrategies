from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from its.ga.engine import run_ga_search
from its.ga.registry import load_alphabet_registry

API_PREFIX = "/api/v1"
DATA_BACKEND_BASE_URL = os.getenv(
    "DATA_BACKEND_BASE_URL",
    "http://data-backend:8000/api/v1",
).rstrip("/")
GA_RUN_CACHE_DIR = Path(os.getenv("GA_RUN_CACHE_DIR", "/app/its/data/ga_runs"))

RUNS: dict[str, dict[str, Any]] = {}
RUNS_LOCK = threading.Lock()


class GARunRequest(BaseModel):
    test_name: str = Field(default="ga_baseline", min_length=1, max_length=80)
    start_date: date
    end_date: date
    interval: str = "CANDLE_INTERVAL_DAY"
    class_code: str = "TQBR"
    test_size: float = Field(default=0.33, ge=0.05, le=0.80)
    num_generations: int = Field(default=10, ge=1, le=100)
    sol_per_pop: int = Field(default=8, ge=2, le=80)
    num_parents_mating: int = Field(default=4, ge=1, le=80)
    mutation_probability: float = Field(default=0.25, ge=0, le=1)
    parent_selection_type: str = "tournament"
    k_tournament: int = Field(default=3, ge=2, le=20)
    keep_parents: int = Field(default=0, ge=-1, le=20)
    keep_elitism: int = Field(default=1, ge=0, le=20)
    crossover_type: str = "uniform"
    mutation_type: str = "random"
    stop_criteria: str = "saturate_3"
    random_seed: int = 42
    cpcv_n_folds: int = Field(default=4, ge=3, le=30)
    cpcv_n_test_folds: int = Field(default=2, ge=2, le=29)
    wf_train_size: int = Field(default=63, ge=2, le=1000)
    wf_test_size: int = Field(default=21, ge=1, le=500)
    wf_purged_size: int = Field(default=5, ge=0, le=250)
    top_n: int = Field(default=3, ge=1, le=10)
    materialize_top: bool = True


def create_app() -> FastAPI:
    app = FastAPI(
        title="ITS GA Backend",
        description="Genetic algorithm strategy generation API",
        version="0.1.0",
        docs_url=f"{API_PREFIX}/docs",
        openapi_url=f"{API_PREFIX}/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get(f"{API_PREFIX}/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get(f"{API_PREFIX}/alphabets")
    async def alphabets() -> dict[str, Any]:
        return load_alphabet_registry()

    @app.get(f"{API_PREFIX}/runs")
    async def list_runs() -> dict[str, Any]:
        with RUNS_LOCK:
            items = [
                summarize_run(run)
                for run in sorted(
                    RUNS.values(),
                    key=lambda item: item.get("created_at", ""),
                    reverse=True,
                )
            ]
        return {"items": items}

    @app.get(f"{API_PREFIX}/runs/{{run_id}}")
    async def get_run(run_id: str) -> dict[str, Any]:
        with RUNS_LOCK:
            run = RUNS.get(run_id)
        if run is None:
            cached = read_cached_run(run_id)
            if cached is None:
                raise HTTPException(status_code=404, detail="GA run was not found.")
            return cached
        return run

    @app.post(f"{API_PREFIX}/runs")
    async def start_run(
        request: GARunRequest,
        background_tasks: BackgroundTasks,
    ) -> dict[str, Any]:
        validate_request(request)
        run_id = f"{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"
        settings = request.model_dump(mode="json")
        settings["run_id"] = run_id
        run = {
            "run_id": run_id,
            "status": "queued",
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
            "settings": settings,
            "events": [],
            "result": None,
            "error": None,
        }
        with RUNS_LOCK:
            RUNS[run_id] = run
        background_tasks.add_task(run_ga_job, run_id, settings)
        return run

    return app


def validate_request(request: GARunRequest) -> None:
    if request.start_date >= request.end_date:
        raise HTTPException(
            status_code=422, detail="start_date must be before end_date."
        )
    if request.cpcv_n_test_folds >= request.cpcv_n_folds:
        raise HTTPException(
            status_code=422,
            detail="cpcv_n_test_folds must be lower than cpcv_n_folds.",
        )
    if request.num_parents_mating > request.sol_per_pop:
        raise HTTPException(
            status_code=422,
            detail="num_parents_mating must be lower than or equal to sol_per_pop.",
        )


def run_ga_job(run_id: str, settings: dict[str, Any]) -> None:
    update_run(run_id, status="running")
    try:
        stocks = fetch_stocks(settings)
        figis = [item["figi"] for item in stocks if item.get("figi")]
        if not figis:
            raise HTTPException(status_code=404, detail="No assets found for GA.")
        prices = fetch_prices(figis, settings)
        if prices.empty:
            raise HTTPException(status_code=404, detail="No prices found for GA.")

        result = run_ga_search(
            prices=prices,
            stocks=stocks,
            settings=settings,
            progress_callback=lambda event: append_event(run_id, event),
        )
        update_run(run_id, status="completed", result=result)
    except Exception as exc:
        update_run(run_id, status="failed", error=repr(exc))
    finally:
        cache_run(run_id)


def fetch_stocks(settings: dict[str, Any]) -> list[dict[str, Any]]:
    with httpx.Client(timeout=60) as client:
        response = client.get(
            f"{DATA_BACKEND_BASE_URL}/stocks",
            params={"class_code": settings["class_code"]},
        )
    payload = handle_data_response(response)
    return payload.get("items", [])


def fetch_prices(figis: list[str], settings: dict[str, Any]) -> pd.DataFrame:
    params: list[tuple[str, str]] = [("figis", figi) for figi in figis] + [
        ("class_code", settings["class_code"]),
        ("start_date", settings["start_date"]),
        ("end_date", settings["end_date"]),
        ("interval", settings["interval"]),
        ("is_complete", "true"),
    ]
    with httpx.Client(timeout=300) as client:
        response = client.get(f"{DATA_BACKEND_BASE_URL}/prices", params=params)
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
        status_code=502, detail=f"Data backend request failed: {detail}"
    )


def append_event(run_id: str, event: dict[str, Any]) -> None:
    with RUNS_LOCK:
        run = RUNS.get(run_id)
        if run is None:
            return
        run["events"].append({"at": datetime.now(UTC).isoformat(), **event})
        run["updated_at"] = datetime.now(UTC).isoformat()


def update_run(
    run_id: str,
    *,
    status: str,
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    with RUNS_LOCK:
        run = RUNS.get(run_id)
        if run is None:
            return
        run["status"] = status
        run["updated_at"] = datetime.now(UTC).isoformat()
        if result is not None:
            run["result"] = result
        if error is not None:
            run["error"] = error


def summarize_run(run: dict[str, Any]) -> dict[str, Any]:
    result = run.get("result") or {}
    top = result.get("top_strategies") or []
    return {
        "run_id": run.get("run_id"),
        "status": run.get("status"),
        "created_at": run.get("created_at"),
        "updated_at": run.get("updated_at"),
        "test_name": run.get("settings", {}).get("test_name"),
        "best_score": top[0].get("TOTAL_SCORE") if top else None,
        "best_strategy": top[0].get("strategy_name") if top else None,
        "materialized_count": len(result.get("materialized") or []),
        "error": run.get("error"),
    }


def cache_run(run_id: str) -> None:
    with RUNS_LOCK:
        run = RUNS.get(run_id)
    if run is None:
        return
    GA_RUN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = GA_RUN_CACHE_DIR / f"{run_id}.json"
    path.write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")


def read_cached_run(run_id: str) -> dict[str, Any] | None:
    path = GA_RUN_CACHE_DIR / f"{run_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
