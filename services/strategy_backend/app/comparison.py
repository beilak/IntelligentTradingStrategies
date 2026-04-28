from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from its.strategies.testing.comparison import compare_latest_strategy_tests

router = APIRouter(prefix="/comparison", tags=["comparison"])


@router.get("/latest")
async def latest_strategy_comparison() -> dict[str, Any]:
    return compare_latest_strategy_tests()
