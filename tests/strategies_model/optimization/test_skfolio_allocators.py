import numpy as np
import pandas as pd
import pytest
from skfolio.optimization import (
    EqualWeighted,
    HierarchicalEqualRiskContribution,
    MaximumDiversification,
    MeanRisk,
    RiskBudgeting,
)
from sklearn.base import clone

from its.ga.registry import load_gene_group
from its.strategies.core.optimization import (
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


@pytest.fixture
def returns() -> pd.DataFrame:
    rng = np.random.default_rng(0)
    return pd.DataFrame(
        rng.normal(0.001, 0.02, size=(200, 5)),
        columns=["AAA", "BBB", "CCC", "DDD", "EEE"],
    )


SUT = [
    (
        "minimum_variance",
        MinimumVarianceAllocator,
        MeanRisk,
    ),
    (
        "maximum_sharpe",
        MaximumSharpeAllocator,
        MeanRisk,
    ),
    (
        "maximum_return",
        MaximumReturnAllocator,
        MeanRisk,
    ),
    (
        "equal_risk_contribution",
        EqualRiskContributionAllocator,
        RiskBudgeting,
    ),
    (
        "minimum_cvar",
        MinimumCVaRAllocator,
        MeanRisk,
    ),
    (
        "mean_cvar",
        MeanCVaRAllocator,
        MeanRisk,
    ),
    (
        "cvar_risk_parity",
        CVaRRiskParityAllocator,
        RiskBudgeting,
    ),
    (
        "maximum_diversification",
        MaximumDiversificationAllocator,
        MaximumDiversification,
    ),
    (
        "hierarchical_equal_risk_contribution",
        HierarchicalEqualRiskContributionAllocator,
        HierarchicalEqualRiskContribution,
    ),
    (
        "nested_clusters_optimization",
        NestedClustersOptimizationAllocator,
        NestedClustersOptimizationAllocator,
    ),
]


@pytest.mark.parametrize("gene_id, cls, _", SUT, ids=[s[0] for s in SUT])
def test_allocator_importable_from_package(gene_id: str, cls: type, _: type) -> None:
    assert (
        cls.__name__
        in __import__("its.strategies.core.optimization", fromlist=["*"]).__all__
    )


@pytest.mark.parametrize("gene_id, cls, base", SUT, ids=[s[0] for s in SUT])
def test_allocator_uses_skfolio_base(gene_id: str, cls: type, base: type) -> None:
    estimator = cls()
    assert isinstance(estimator, base)


@pytest.mark.parametrize("gene_id, cls, _", SUT, ids=[s[0] for s in SUT])
def test_allocator_is_clone_compatible(gene_id: str, cls: type, _: type) -> None:
    cloned = clone(cls(raise_on_failure=False))
    assert isinstance(cloned, cls)


@pytest.mark.parametrize("gene_id, cls, _", SUT, ids=[s[0] for s in SUT])
def test_allocator_fits_and_produces_valid_weights(
    returns: pd.DataFrame,
    gene_id: str,
    cls: type,
    _: type,
) -> None:
    estimator = cls(raise_on_failure=False).fit(returns)
    weights = estimator.weights_
    assert weights.shape == (returns.shape[1],)
    assert np.isfinite(weights).all()
    assert not np.isnan(weights).any()
    assert not np.isinf(weights).any()
    assert weights.sum() == pytest.approx(1.0, abs=1e-4)


@pytest.mark.parametrize("gene_id, cls, _", SUT, ids=[s[0] for s in SUT])
def test_allocator_registered_in_ga_alphabet(
    gene_id: str,
    cls: type,
    _: type,
) -> None:
    gene_ids = {gene.id for gene in load_gene_group("allocation")}
    assert gene_id in gene_ids


def test_equal_risk_contribution_uses_risk_budgeting_not_inverse_volatility(
    returns: pd.DataFrame,
) -> None:
    from skfolio.optimization import InverseVolatility

    estimator = EqualRiskContributionAllocator(raise_on_failure=False).fit(returns)
    assert not isinstance(estimator, InverseVolatility)
    assert isinstance(estimator, RiskBudgeting)


def test_minimum_cvar_uses_mean_risk_not_custom_cvar(returns: pd.DataFrame) -> None:
    from its.strategies.core.optimization import CVaR, MeanCVaRAllocator

    estimator = MinimumCVaRAllocator(raise_on_failure=False).fit(returns)
    assert isinstance(estimator, MeanRisk)
    assert not isinstance(estimator, CVaR)
    assert not isinstance(estimator, MeanCVaRAllocator)


def test_cvar_risk_parity_uses_risk_budgeting(returns: pd.DataFrame) -> None:
    estimator = CVaRRiskParityAllocator(raise_on_failure=False).fit(returns)
    assert isinstance(estimator, RiskBudgeting)


def test_cvar_risk_parity_can_fall_back_to_equal_weights(
    returns: pd.DataFrame,
) -> None:
    estimator = CVaRRiskParityAllocator(
        solver="SCIPY",
        fallback=EqualWeighted(),
    ).fit(returns)

    assert isinstance(estimator.fallback_, EqualWeighted)
    assert estimator.weights_ == pytest.approx(np.full(returns.shape[1], 0.2))


def test_erc_differs_from_inverse_volatility(returns: pd.DataFrame) -> None:
    from skfolio.optimization import InverseVolatility

    erc = EqualRiskContributionAllocator(raise_on_failure=False).fit(returns)
    inv = InverseVolatility(raise_on_failure=False).fit(returns)
    assert not np.allclose(erc.weights_, inv.weights_)


def test_minimum_cvar_minimizes_cvar(returns: pd.DataFrame) -> None:
    from skfolio.measures import cvar

    def portfolio_cvar(weights: np.ndarray) -> float:
        return cvar((returns * weights).sum(axis=1), beta=0.95)

    min_cvar = MinimumCVaRAllocator(raise_on_failure=False).fit(returns)
    max_sharpe = MaximumSharpeAllocator(raise_on_failure=False).fit(returns)
    assert portfolio_cvar(min_cvar.weights_) <= portfolio_cvar(max_sharpe.weights_)
