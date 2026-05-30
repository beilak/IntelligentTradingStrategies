from typing import override

from its.strategies.core.optimization import EqualWeighted
from its.strategies.core.selectors import (
    IntradayTurnoverSelector,
    SafeEmptySelector,
    TrendThresholdSelector,
)
from its.strategies.core.types.strategy_types import Pipeline, Strategy, StrategyBuilder


class GAGenerated202604282213283178fbd4Top2Builder(StrategyBuilder):
    """Materialized GA strategy generated at 2026-04-28T22:13:38.766271+00:00."""

    TURNOVER_LOOKBACK_BARS = 10
    MIN_TURNOVER_RUB = 1_000_000
    SIGNAL_WINDOW = 40
    SIGNAL_SLOPE_THRESHOLD = 0.0

    @override
    def build(self) -> Strategy:
        return Strategy(
            name="[GA][turnover_1m_10][trend_threshold_40][equal_weighted]",
            description=(
                "GA materialized strategy. Selector=turnover_1m_10; "
                "Signal=trend_threshold_40; Allocation=equal_weighted; "
                "TOTAL_SCORE=15.253065052139569."
            ),
            pipeline=Pipeline(
                steps=[
                    (
                        "ga_pre_selection",
                        IntradayTurnoverSelector(
                            asset_universe_prices=self._asset_universe_prices,
                            lookback_bars=self.TURNOVER_LOOKBACK_BARS,
                            min_turnover=self.MIN_TURNOVER_RUB,
                            allow_empty_selection=False,
                        ),
                    ),
                    (
                        "ga_signal",
                        SafeEmptySelector(
                            TrendThresholdSelector(
                                window=self.SIGNAL_WINDOW,
                                slope_threshold=self.SIGNAL_SLOPE_THRESHOLD,
                            )
                        ),
                    ),
                    (
                        "ga_allocation",
                        EqualWeighted(),
                    ),
                ]
            ),
        )
