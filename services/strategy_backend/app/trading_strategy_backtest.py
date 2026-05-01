from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from its.strategies.testing.backtest import (
    cache_path,
    generate_trading_strategy_backtest_report,
    list_test_paths,
    read_json,
    read_test_summary,
)
from services.strategy_backend.app.backtest import (
    BacktestRunRequest,
    enrich_cached_backtest,
    run_backtest_flow,
)

router = APIRouter(
    prefix="/trading-strategies/{strategy_name}/backtest",
    tags=["trading-strategy-backtest"],
)


@router.get("/tests")
async def list_trading_strategy_backtest_tests(strategy_name: str) -> dict[str, Any]:
    subject = cache_subject(strategy_name)
    return {"items": [read_test_summary(path) for path in list_test_paths(subject)]}


@router.get("/tests/{test_name}")
async def get_trading_strategy_backtest_test(
    strategy_name: str,
    test_name: str,
) -> dict[str, Any]:
    path = cache_path(cache_subject(strategy_name), test_name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Backtest cache was not found.")
    return await enrich_cached_backtest(read_json(path))


@router.post("/run")
async def run_trading_strategy_backtest_test(
    strategy_name: str,
    request: BacktestRunRequest,
) -> dict[str, Any]:
    return await run_backtest_flow(
        subject_name=strategy_name,
        request=request,
        output_path=cache_path(cache_subject(strategy_name), request.test_name),
        report_factory=generate_trading_strategy_backtest_report,
    )


def cache_subject(strategy_name: str) -> str:
    return f"trading_strategy.{strategy_name}"
