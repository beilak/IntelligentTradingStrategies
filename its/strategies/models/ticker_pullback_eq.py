from typing import override

from its.strategies.core.optimization import EqualWeighted
from its.strategies.core.selectors import SafeEmptySelector, TickerSelector
from its.strategies.core.signals import CloseBelowRecentMarkerSignal
from its.strategies.core.types.strategy_types import Pipeline, Strategy, StrategyBuilder


class ModelPullbackWithEQBuilder(StrategyBuilder):
    """Build an explicit ticker pullback strategy with equal-weight allocation."""

    TICKERS = ["SBER", "TRNFP"]
    MARKER = "high"
    LOOKBACK_BARS = 10
    THRESHOLD_PCT = 0.01

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
                        "ticker_pre_selection",
                        TickerSelector(
                            tickers=self.TICKERS,
                            allow_empty_selection=False,
                        ),
                    ),
                    (
                        "pullback_signal",
                        SafeEmptySelector(
                            CloseBelowRecentMarkerSignal(
                                marker=self.MARKER,
                                lookback_bars=self.LOOKBACK_BARS,
                                threshold_pct=self.THRESHOLD_PCT,
                                asset_universe_prices=self._asset_universe_prices,
                            ),
                        ),
                    ),
                    ("allocation", EqualWeighted()),
                ]
            ),
        )
