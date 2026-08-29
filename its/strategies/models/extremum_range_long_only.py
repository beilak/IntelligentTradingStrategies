from typing import override

from its.strategies.core.optimization import EqualWeightedWithCash
from its.strategies.core.selectors import QuarterlyTopTurnoverSelector
from its.strategies.core.signals import ExtremumRangeLongSignal
from its.strategies.core.types.strategy_types import Pipeline, Strategy, StrategyBuilder


class ModelExtremumRangeLongOnlyBuilder(StrategyBuilder):
    """Build the frozen FAST long-only Extremum Range portfolio core."""

    TOP_N = 100
    TURNOVER_LOOKBACK_DAYS = 10
    CHANNEL_LOOKBACK_BARS = 30
    EMA_LENGTH = 500
    EMA_STREAK_LENGTH = 50
    ALLOCATION_PCT = 0.95

    @override
    def build(self) -> Strategy:
        return Strategy(
            name="Extremum_range_long_only",
            description=(
                f"Quarterly top-{self.TOP_N} by trailing "
                f"{self.TURNOVER_LOOKBACK_DAYS}-day turnover; long breakouts of "
                f"the prior {self.CHANNEL_LOOKBACK_BARS}-bar high after an "
                f"EMA({self.EMA_LENGTH}) {self.EMA_STREAK_LENGTH}-bar side streak; "
                f"allocate {self.ALLOCATION_PCT:.0%} equally and keep the rest in cash"
            ),
            pipeline=Pipeline(
                steps=[
                    (
                        "quarterly_turnover_pre_selection",
                        QuarterlyTopTurnoverSelector(
                            asset_universe_prices=self._asset_universe_prices,
                            top_n=self.TOP_N,
                            lookback_days=self.TURNOVER_LOOKBACK_DAYS,
                            min_history_days=self.TURNOVER_LOOKBACK_DAYS,
                        ),
                    ),
                    (
                        "extremum_range_long_signal",
                        ExtremumRangeLongSignal(
                            asset_universe_prices=self._asset_universe_prices,
                            channel_lookback_bars=self.CHANNEL_LOOKBACK_BARS,
                            ema_length=self.EMA_LENGTH,
                            streak_length=self.EMA_STREAK_LENGTH,
                            gate_side="either",
                        ),
                    ),
                    (
                        "allocation",
                        EqualWeightedWithCash(
                            allocation_pct=self.ALLOCATION_PCT,
                        ),
                    ),
                ]
            ),
        )
