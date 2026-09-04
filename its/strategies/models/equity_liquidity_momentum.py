from abc import ABC, abstractmethod
from typing import override

from its.strategies.core.optimization import (
    CVaRRiskParityAllocator,
    EqualRiskContributionAllocator,
    EqualWeighted,
    HierarchicalEqualRiskContributionAllocator,
    HierarchicalRiskParity,
    InverseVolatility,
    MaximumDiversificationAllocator,
    MaximumSharpeAllocator,
    MinimumCVaRAllocator,
    MinimumVarianceAllocator,
)
from its.strategies.core.selectors import EquityLiquiditySelector
from its.strategies.core.signals import LongOnlyCrossSectionalMomentumSignal
from its.strategies.core.types.strategy_types import Pipeline, Strategy, StrategyBuilder


class _EquityLiquidityMomentumBase(StrategyBuilder, ABC):
    """Shared composition for liquidity + momentum strategies.

    The pipeline is identical across all strategies in the family and differs
    only in the final weight allocator, supplied by :meth:`_make_allocator`.
    """

    LIQUIDITY_LOOKBACK_DAYS = 63
    MIN_AVG_DAILY_TURNOVER_RUB = 10_000_000
    MOMENTUM_LOOKBACK_DAYS = 252
    MOMENTUM_SKIP_LAST_DAYS = 21
    MOMENTUM_TOP_N = 10

    name: str

    @abstractmethod
    def _make_allocator(self):
        """Return the allocator used as the final pipeline step."""

    @override
    def build(self) -> Strategy:
        return Strategy(
            name=self.name,
            description=(
                "Equities kept when trailing mean daily ruble turnover over the "
                f"prior {self.LIQUIDITY_LOOKBACK_DAYS} days is at least "
                f"{self.MIN_AVG_DAILY_TURNOVER_RUB}; then the top-"
                f"{self.MOMENTUM_TOP_N} by {self.MOMENTUM_LOOKBACK_DAYS}-day "
                f"cross-sectional momentum (skipping {self.MOMENTUM_SKIP_LAST_DAYS} "
                "days) are allocated by " + self._allocator_description()
            ),
            pipeline=Pipeline(
                steps=[
                    (
                        "equity_liquidity_pre_selection",
                        EquityLiquiditySelector(
                            asset_universe_prices=self._asset_universe_prices,
                            lookback_days=self.LIQUIDITY_LOOKBACK_DAYS,
                            min_avg_daily_turnover_rub=self.MIN_AVG_DAILY_TURNOVER_RUB,
                            min_history_days=self.LIQUIDITY_LOOKBACK_DAYS,
                        ),
                    ),
                    (
                        "long_only_momentum_signal",
                        LongOnlyCrossSectionalMomentumSignal(
                            asset_universe_prices=self._asset_universe_prices,
                            lookback_days=self.MOMENTUM_LOOKBACK_DAYS,
                            skip_last_days=self.MOMENTUM_SKIP_LAST_DAYS,
                            top_n=self.MOMENTUM_TOP_N,
                        ),
                    ),
                    ("allocation", self._make_allocator()),
                ]
            ),
        )


class ModelEquityLiquidityMomentumEqualWeightBuilder(_EquityLiquidityMomentumBase):
    """Liquidity + momentum with equal-weight allocation."""

    name = "EquityLiquidityMomentumEqualWeight"

    def _allocator_description(self) -> str:
        return "equal weights"

    def _make_allocator(self):
        return EqualWeighted()


class ModelEquityLiquidityMomentumInverseVolatilityBuilder(
    _EquityLiquidityMomentumBase
):
    """Liquidity + momentum with inverse-volatility allocation."""

    name = "EquityLiquidityMomentumInverseVolatility"

    def _allocator_description(self) -> str:
        return "weights inversely proportional to historical volatility"

    def _make_allocator(self):
        return InverseVolatility()


class ModelEquityLiquidityMomentumMinimumVarianceBuilder(_EquityLiquidityMomentumBase):
    """Liquidity + momentum with minimum-variance allocation."""

    name = "EquityLiquidityMomentumMinimumVariance"

    def _allocator_description(self) -> str:
        return "the minimum portfolio variance"

    def _make_allocator(self):
        return MinimumVarianceAllocator()


class ModelEquityLiquidityMomentumMaximumSharpeBuilder(_EquityLiquidityMomentumBase):
    """Liquidity + momentum with maximum-Sharpe allocation."""

    name = "EquityLiquidityMomentumMaximumSharpe"

    def _allocator_description(self) -> str:
        return "the maximum expected-return/volatility ratio"

    def _make_allocator(self):
        return MaximumSharpeAllocator()


class ModelEquityLiquidityMomentumEqualRiskContributionBuilder(
    _EquityLiquidityMomentumBase
):
    """Liquidity + momentum with equal-risk-contribution allocation."""

    name = "EquityLiquidityMomentumEqualRiskContribution"

    def _allocator_description(self) -> str:
        return "an equal contribution of every asset to portfolio risk"

    def _make_allocator(self):
        return EqualRiskContributionAllocator()


class ModelEquityLiquidityMomentumMaximumDiversificationBuilder(
    _EquityLiquidityMomentumBase
):
    """Liquidity + momentum with maximum-diversification allocation."""

    name = "EquityLiquidityMomentumMaximumDiversification"

    def _allocator_description(self) -> str:
        return "the maximum portfolio diversification ratio"

    def _make_allocator(self):
        return MaximumDiversificationAllocator()


class ModelEquityLiquidityMomentumMinimumCVaRBuilder(_EquityLiquidityMomentumBase):
    """Liquidity + momentum with minimum-CVaR allocation."""

    name = "EquityLiquidityMomentumMinimumCVaR"

    def _allocator_description(self) -> str:
        return "the minimum portfolio Conditional Value-at-Risk"

    def _make_allocator(self):
        return MinimumCVaRAllocator()


class ModelEquityLiquidityMomentumCVaRRiskParityBuilder(_EquityLiquidityMomentumBase):
    """Liquidity + momentum with CVaR risk-parity allocation."""

    name = "EquityLiquidityMomentumCVaRRiskParity"

    def _allocator_description(self) -> str:
        return "an equal contribution of every asset to portfolio CVaR risk"

    def _make_allocator(self):
        return CVaRRiskParityAllocator(fallback=EqualWeighted())


class ModelEquityLiquidityMomentumHRPBuilder(_EquityLiquidityMomentumBase):
    """Liquidity + momentum with hierarchical risk-parity allocation."""

    name = "EquityLiquidityMomentumHRP"

    def _allocator_description(self) -> str:
        return "hierarchical risk parity"

    def _make_allocator(self):
        return HierarchicalRiskParity()


class ModelEquityLiquidityMomentumHERCBuilder(_EquityLiquidityMomentumBase):
    """Liquidity + momentum with hierarchical equal-risk-contribution allocation."""

    name = "EquityLiquidityMomentumHERC"

    def _allocator_description(self) -> str:
        return "hierarchical equal risk contribution"

    def _make_allocator(self):
        return HierarchicalEqualRiskContributionAllocator()
