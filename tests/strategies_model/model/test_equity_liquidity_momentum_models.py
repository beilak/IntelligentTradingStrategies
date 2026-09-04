import numpy as np
import pandas as pd
import pytest
import skfolio.optimization as skopt

from its.strategies.core.optimization import (
    CVaRRiskParityAllocator,
    EqualRiskContributionAllocator,
    EqualWeighted,
    HierarchicalEqualRiskContributionAllocator,
    MaximumDiversificationAllocator,
    MaximumSharpeAllocator,
    MinimumCVaRAllocator,
    MinimumVarianceAllocator,
)
from its.strategies.core.selectors import EquityLiquiditySelector
from its.strategies.core.signals import LongOnlyCrossSectionalMomentumSignal
from its.strategies.models import (
    ModelEquityLiquidityMomentumCVaRRiskParityBuilder,
    ModelEquityLiquidityMomentumEqualRiskContributionBuilder,
    ModelEquityLiquidityMomentumEqualWeightBuilder,
    ModelEquityLiquidityMomentumHERCBuilder,
    ModelEquityLiquidityMomentumHRPBuilder,
    ModelEquityLiquidityMomentumInverseVolatilityBuilder,
    ModelEquityLiquidityMomentumMaximumDiversificationBuilder,
    ModelEquityLiquidityMomentumMaximumSharpeBuilder,
    ModelEquityLiquidityMomentumMinimumCVaRBuilder,
    ModelEquityLiquidityMomentumMinimumVarianceBuilder,
)
from its.strategies.testing.backtest.vectorbt_backtest import (
    backtest_strategies_vectorbt,
)

TICKERS = ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"]


def build_fixture() -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = pd.bdate_range("2019-01-01", periods=600)
    rng = np.random.default_rng(7)
    close = pd.DataFrame(index=dates)
    for ticker in TICKERS:
        close[ticker] = 100.0 * np.exp(
            np.cumsum(rng.normal(0.001, 0.015, size=len(dates)))
        )
    context = pd.DataFrame(
        [
            {
                "time": date,
                "ticker": ticker,
                "open": value,
                "high": value * 1.01,
                "low": value * 0.99,
                "close": value,
                "volume": 50_000_000.0,
                "is_complete": True,
            }
            for date in dates
            for ticker in TICKERS
            for value in (float(close.loc[date, ticker]),)
        ]
    )
    return close, context


BUILDERS = [
    (
        "EquityLiquidityMomentumEqualWeight",
        ModelEquityLiquidityMomentumEqualWeightBuilder,
        EqualWeighted,
    ),
    (
        "EquityLiquidityMomentumInverseVolatility",
        ModelEquityLiquidityMomentumInverseVolatilityBuilder,
        skopt.InverseVolatility,
    ),
    (
        "EquityLiquidityMomentumMinimumVariance",
        ModelEquityLiquidityMomentumMinimumVarianceBuilder,
        MinimumVarianceAllocator,
    ),
    (
        "EquityLiquidityMomentumMaximumSharpe",
        ModelEquityLiquidityMomentumMaximumSharpeBuilder,
        MaximumSharpeAllocator,
    ),
    (
        "EquityLiquidityMomentumEqualRiskContribution",
        ModelEquityLiquidityMomentumEqualRiskContributionBuilder,
        EqualRiskContributionAllocator,
    ),
    (
        "EquityLiquidityMomentumMaximumDiversification",
        ModelEquityLiquidityMomentumMaximumDiversificationBuilder,
        MaximumDiversificationAllocator,
    ),
    (
        "EquityLiquidityMomentumMinimumCVaR",
        ModelEquityLiquidityMomentumMinimumCVaRBuilder,
        MinimumCVaRAllocator,
    ),
    (
        "EquityLiquidityMomentumCVaRRiskParity",
        ModelEquityLiquidityMomentumCVaRRiskParityBuilder,
        CVaRRiskParityAllocator,
    ),
    (
        "EquityLiquidityMomentumHRP",
        ModelEquityLiquidityMomentumHRPBuilder,
        skopt.HierarchicalRiskParity,
    ),
    (
        "EquityLiquidityMomentumHERC",
        ModelEquityLiquidityMomentumHERCBuilder,
        HierarchicalEqualRiskContributionAllocator,
    ),
]


@pytest.mark.parametrize("name, builder_cls, allocator_cls", BUILDERS)
def test_model_composition_and_frozen_parameters(
    name: str,
    builder_cls: type,
    allocator_cls: type,
) -> None:
    _, context = build_fixture()
    strategy = builder_cls(context).build()

    assert strategy.name == name
    assert [step for step, _ in strategy.pipeline.steps] == [
        "equity_liquidity_pre_selection",
        "long_only_momentum_signal",
        "allocation",
    ]
    selector = strategy.pipeline.named_steps["equity_liquidity_pre_selection"]
    signal = strategy.pipeline.named_steps["long_only_momentum_signal"]
    allocator = strategy.pipeline.named_steps["allocation"]
    assert isinstance(selector, EquityLiquiditySelector)
    assert isinstance(signal, LongOnlyCrossSectionalMomentumSignal)
    assert isinstance(allocator, allocator_cls)
    assert selector.lookback_days == 63
    assert selector.min_avg_daily_turnover_rub == 10_000_000
    assert signal.lookback_days == 252
    assert signal.skip_last_days == 21
    assert signal.top_n == 10


@pytest.mark.parametrize("name, builder_cls, _", BUILDERS)
def test_models_exported_from_package(name: str, builder_cls: type, _: type) -> None:
    from its.strategies import models

    assert builder_cls.__name__ in models.__all__
    assert getattr(models, builder_cls.__name__) is builder_cls


def test_all_models_allocate_in_backtest() -> None:
    prices, context = build_fixture()
    strategies = {
        strategy_name: builder_cls(context).build()
        for strategy_name, builder_cls, _ in BUILDERS
    }

    results = backtest_strategies_vectorbt(
        strategies=strategies,
        prices=prices,
        rebalance_freq=21,
        rebalance_on="last",
        trading_start_date=prices.index[400],
        freq="1D",
    )

    assert set(results) == set(strategies)
    for result in results.values():
        weights = result.weights.dropna(how="all")
        assert not weights.empty
        assert np.isfinite(weights.to_numpy()).all()
        assert (weights.sum(axis=1) > 1e-6).any()
        assert np.allclose(weights.sum(axis=1), 1.0, atol=1e-3)


def test_cvar_risk_parity_model_falls_back_to_equal_weights() -> None:
    _, context = build_fixture()
    strategy = ModelEquityLiquidityMomentumCVaRRiskParityBuilder(context).build()
    allocator = strategy.pipeline.named_steps["allocation"]

    assert isinstance(allocator.fallback, EqualWeighted)
