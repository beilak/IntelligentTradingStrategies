from typing import override

from its.strategies.core.optimization import InverseVolatility
from its.strategies.core.selectors import IntradayTurnoverSelector
from its.strategies.core.types.strategy_types import Pipeline, Strategy, StrategyBuilder


class ModelTurnoverWithInverseVolatilityBuilder(StrategyBuilder):
    """Build a turnover-filtered strategy with InverseVolatility allocation."""

    TURNOVER_LOOKBACK_BARS = 10
    MIN_TURNOVER_RUB = 1_000_000

    @override
    def build(self) -> Strategy:
        return Strategy(
            name="Turnover_with_InverseVolatility",
            description=f"Min Turnover {self.MIN_TURNOVER_RUB} for last MIN_TURNOVER_RUB. Allocation is InverseVolatility",
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
                    ("allocation", InverseVolatility()),
                ]
            ),
        )
