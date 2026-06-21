from typing import override

from its.strategies.core.optimization import CQMAllocator
from its.strategies.core.selectors import IntradayTurnoverSelector
from its.strategies.core.types.strategy_types import Pipeline, Strategy, StrategyBuilder


class ModelTurnoverWithCQMBuilder(StrategyBuilder):
    """Build a turnover-filtered strategy with CQM allocation."""

    TURNOVER_LOOKBACK_BARS = 10
    MIN_TURNOVER_RUB = 1_000_000

    @override
    def build(self) -> Strategy:
        return Strategy(
            name="Turnover_with_CQM",
            description=(
                f"Min Turnover {self.MIN_TURNOVER_RUB} for last MIN_TURNOVER_RUB. "
                "Allocation is CQM"
            ),
            pipeline=Pipeline(
                steps=[
                    (
                        "turnover_pre_selection",
                        IntradayTurnoverSelector(
                            asset_universe_prices=self._asset_universe_prices,
                            lookback_bars=self.TURNOVER_LOOKBACK_BARS,
                            min_turnover=self.MIN_TURNOVER_RUB,
                        ),
                    ),
                    (
                        "allocation",
                        CQMAllocator(
                            max_weight=0.5,
                            weight_unit=0.05,
                            alpha_weight=1.0,
                            risk_weight=1.0,
                            deviation_weight=1.0,
                            concentration_weight=0.25,
                        ),
                    ),
                ]
            ),
        )


class ModelHighTurnoverWithCQMBuilder(StrategyBuilder):
    """Build a high-turnover-filtered strategy with CQM allocation."""

    TURNOVER_LOOKBACK_BARS = 2
    MIN_TURNOVER_RUB = 100_000_000

    @override
    def build(self) -> Strategy:
        return Strategy(
            name="High_Turnover_with_CQM",
            description=(
                f"Min Turnover {self.MIN_TURNOVER_RUB} for last MIN_TURNOVER_RUB. "
                "Allocation is CQM"
            ),
            pipeline=Pipeline(
                steps=[
                    (
                        "turnover_pre_selection",
                        IntradayTurnoverSelector(
                            asset_universe_prices=self._asset_universe_prices,
                            lookback_bars=self.TURNOVER_LOOKBACK_BARS,
                            min_turnover=self.MIN_TURNOVER_RUB,
                        ),
                    ),
                    (
                        "allocation",
                        CQMAllocator(
                            max_weight=0.5,
                            weight_unit=0.05,
                            alpha_weight=1.0,
                            risk_weight=1.0,
                            deviation_weight=1.0,
                            concentration_weight=0.25,
                        ),
                    ),
                ]
            ),
        )
