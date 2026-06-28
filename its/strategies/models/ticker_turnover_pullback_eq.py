from typing import override

from its.strategies.core.optimization import EqualWeighted
from its.strategies.core.selectors import IntradayTurnoverSelector, TickerSelector
from its.strategies.core.signals import CloseBelowRecentMarkerSignal
from its.strategies.core.types.strategy_types import Pipeline, Strategy, StrategyBuilder


class ModelTurnoverPullbackWithEQBuilder(StrategyBuilder):
    """Build an explicit ticker pullback strategy with equal-weight allocation."""

    MARKER = "high"
    LOOKBACK_BARS = 10
    THRESHOLD_PCT = 0.01

    TURNOVER_LOOKBACK_BARS = 2
    MIN_TURNOVER_RUB = 1_000_000_000

    @override
    def build(self) -> Strategy:
        return Strategy(
            name="Pullback_with_EQ",
            description=(
                "Select tickers, buy when close is at least "
                f"{self.THRESHOLD_PCT:.0%} below recent {self.MARKER}, "
                "allocate Equal Weighted"
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
                        "pullback_signal",
                        CloseBelowRecentMarkerSignal(
                            marker=self.MARKER,
                            lookback_bars=self.LOOKBACK_BARS,
                            threshold_pct=self.THRESHOLD_PCT,
                            asset_universe_prices=self._asset_universe_prices,
                        ),
                    ),
                    ("allocation", EqualWeighted()),
                ]
            ),
        )
