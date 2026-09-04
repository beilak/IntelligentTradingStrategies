from skfolio.moments import EmpiricalCovariance
from skfolio.optimization import EqualWeighted
from skfolio.optimization import HierarchicalRiskParity as SkfolioHierarchicalRiskParity
from skfolio.optimization import InverseVolatility as SkfolioInverseVolatility
from skfolio.prior import EmpiricalPrior

from its.strategies.core.optimization.cqm_allocator import CQMAllocator
from its.strategies.core.optimization.cvar_allocator import CVaR, CVaRHighRisk
from its.strategies.core.optimization.equal_weighted_with_cash import (
    EqualWeightedWithCash,
)
from its.strategies.core.optimization.skfolio_allocators import (
    CVaRRiskParityAllocator,
    EqualRiskContributionAllocator,
    HierarchicalEqualRiskContributionAllocator,
    MaximumDiversificationAllocator,
    MaximumReturnAllocator,
    MaximumSharpeAllocator,
    MeanCVaRAllocator,
    MinimumCVaRAllocator,
    MinimumVarianceAllocator,
    NestedClustersOptimizationAllocator,
)


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
    "CQMAllocator",
    "CVaR",
    "CVaRHighRisk",
    "CVaRRiskParityAllocator",
    "EqualRiskContributionAllocator",
    "EqualWeighted",
    "EqualWeightedWithCash",
    "HierarchicalEqualRiskContributionAllocator",
    "HierarchicalRiskParity",
    "InverseVolatility",
    "MaximumDiversificationAllocator",
    "MaximumReturnAllocator",
    "MaximumSharpeAllocator",
    "MeanCVaRAllocator",
    "MinimumCVaRAllocator",
    "MinimumVarianceAllocator",
    "NestedClustersOptimizationAllocator",
]
