from skfolio.optimization import (
    EqualWeighted,
    InverseVolatility as SkfolioInverseVolatility,
)
from skfolio.optimization import (
    HierarchicalRiskParity as SkfolioHierarchicalRiskParity,
)

from its.strategies.core.optimization.cvar_allocator import CVaR, CVaRHighRisk


def HierarchicalRiskParity(*args, **kwargs) -> SkfolioHierarchicalRiskParity:
    kwargs.setdefault("fallback", EqualWeighted())
    return SkfolioHierarchicalRiskParity(*args, **kwargs)


def InverseVolatility(*args, **kwargs) -> SkfolioInverseVolatility:
    kwargs.setdefault("fallback", EqualWeighted())
    return SkfolioInverseVolatility(*args, **kwargs)


__all__ = [
    "EqualWeighted",
    "InverseVolatility",
    "HierarchicalRiskParity",
    "CVaR",
    "CVaRHighRisk",
]
