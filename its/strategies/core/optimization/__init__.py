from skfolio.optimization import (
    EqualWeighted,
    InverseVolatility,
)
from skfolio.optimization import (
    HierarchicalRiskParity as SkfolioHierarchicalRiskParity,
)

from its.strategies.core.optimization.cvar_allocator import CVaR, CVaRHighRisk


def HierarchicalRiskParity(*args, **kwargs) -> SkfolioHierarchicalRiskParity:
    kwargs.setdefault("fallback", EqualWeighted())
    return SkfolioHierarchicalRiskParity(*args, **kwargs)


__all__ = [
    "EqualWeighted",
    "InverseVolatility",
    "HierarchicalRiskParity",
    "CVaR",
    "CVaRHighRisk",
]
