from skfolio.moments import EmpiricalCovariance
from skfolio.optimization import EqualWeighted
from skfolio.optimization import \
    HierarchicalRiskParity as SkfolioHierarchicalRiskParity
from skfolio.optimization import InverseVolatility as SkfolioInverseVolatility
from skfolio.prior import EmpiricalPrior

from its.strategies.core.optimization.cqm_allocator import CQMAllocator
from its.strategies.core.optimization.cvar_allocator import CVaR, CVaRHighRisk


def HierarchicalRiskParity(*args, **kwargs) -> SkfolioHierarchicalRiskParity:
    kwargs.setdefault("fallback", EqualWeighted())
    return SkfolioHierarchicalRiskParity(*args, **kwargs)


def InverseVolatility(*args, **kwargs) -> SkfolioInverseVolatility:
    kwargs.setdefault(
        "prior_estimator",
        EmpiricalPrior(covariance_estimator=EmpiricalCovariance(nearest=False)),
    )
    kwargs.setdefault("fallback", EqualWeighted())
    return SkfolioInverseVolatility(*args, **kwargs)


__all__ = [
    "EqualWeighted",
    "InverseVolatility",
    "HierarchicalRiskParity",
    "CVaR",
    "CVaRHighRisk",
    "CQMAllocator",
]
