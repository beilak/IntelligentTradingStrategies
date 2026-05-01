from skfolio.optimization import (
    EqualWeighted,
    HierarchicalRiskParity as SkfolioHierarchicalRiskParity,
    InverseVolatility,
)


def HierarchicalRiskParity(*args, **kwargs):
    kwargs.setdefault("fallback", EqualWeighted())
    return SkfolioHierarchicalRiskParity(*args, **kwargs)


__all__ = ["EqualWeighted", "InverseVolatility", "HierarchicalRiskParity"]
