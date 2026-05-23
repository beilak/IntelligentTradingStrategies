from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from its.authz.context import AuthContext
from its.authz.dependencies import require_permissions
from its.authz.permissions import Permissions
from its.strategies.testing.comparison import compare_latest_strategy_tests

router = APIRouter(prefix="/comparison", tags=["comparison"])


@router.get("/latest")
async def latest_strategy_comparison(
    _auth: AuthContext = Depends(
        require_permissions(Permissions.STRATEGY_COMPARE_READ)
    ),
) -> dict[str, Any]:
    return compare_latest_strategy_tests()
