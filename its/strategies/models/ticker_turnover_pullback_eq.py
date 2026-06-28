from typing import override

from sklearn.preprocessing import FunctionTransformer

from its.strategies.core.optimization import EqualWeighted, InverseVolatility
from its.strategies.core.selectors import IntradayTurnoverSelector
from its.strategies.core.signals import (
    AutoRegressionGrowthSignal,
    CloseBelowRecentMarkerSignal,
    RangeLowProximitySignal,
)
from its.strategies.core.types.strategy_types import Pipeline, Strategy, StrategyBuilder


def _recent_rows(values, *, bars: int):
    return values.iloc[-bars:] if hasattr(values, "iloc") else values[-bars:]


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


class ModelTurnoverRangePullbackWithInverseVolatilityBuilder(StrategyBuilder):
    """Select liquid assets near the low of a sufficiently wide recent range."""

    LOOKBACK_BARS = 7
    MIN_RANGE_PCT = 0.05
    MAX_CLOSE_TO_LOW_PCT = 0.02
    TURNOVER_LOOKBACK_BARS = 2
    MIN_TURNOVER_RUB = 10_000_000

    @override
    def build(self) -> Strategy:
        return Strategy(
            name="Turnover_range_pullback_with_inverse_volatility",
            description=(
                f"Select liquid assets with a {self.MIN_RANGE_PCT:.0%}+ range "
                f"over {self.LOOKBACK_BARS} bars and close within "
                f"{self.MAX_CLOSE_TO_LOW_PCT:.0%} of the range low; "
                "allocate by inverse volatility"
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
                        "range_low_proximity_signal",
                        RangeLowProximitySignal(
                            lookback_bars=self.LOOKBACK_BARS,
                            min_range_pct=self.MIN_RANGE_PCT,
                            max_close_to_low_pct=self.MAX_CLOSE_TO_LOW_PCT,
                            asset_universe_prices=self._asset_universe_prices,
                        ),
                    ),
                    ("allocation", InverseVolatility()),
                ]
            ),
        )


class ModelTurnoverAutoRegressionWithInverseVolatilityBuilder(StrategyBuilder):
    """Select liquid assets with a positive autoregression forecast."""

    AUTOREGRESSION_LOOKBACK_BARS = 7
    AUTOREGRESSION_LAGS = 2
    FORECAST_BARS = 2
    MIN_PREDICTED_GROWTH_PCT = 0.01
    TURNOVER_LOOKBACK_BARS = 1
    MIN_TURNOVER_RUB = 10_000_000

    @override
    def build(self) -> Strategy:
        return Strategy(
            name="Turnover_autoregression_with_inverse_volatility",
            description=(
                f"Select liquid assets whose AutoReg({self.AUTOREGRESSION_LAGS}) "
                f"forecast over {self.FORECAST_BARS} bar(s), trained on the last "
                f"{self.AUTOREGRESSION_LOOKBACK_BARS} bars, is at least "
                f"{self.MIN_PREDICTED_GROWTH_PCT:.0%}; allocate by inverse volatility"
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
                        "autoregression_growth_signal",
                        AutoRegressionGrowthSignal(
                            lookback_bars=self.AUTOREGRESSION_LOOKBACK_BARS,
                            lags=self.AUTOREGRESSION_LAGS,
                            forecast_bars=self.FORECAST_BARS,
                            min_growth_pct=self.MIN_PREDICTED_GROWTH_PCT,
                        ),
                    ),
                    (
                        "allocation_window",
                        FunctionTransformer(
                            _recent_rows,
                            kw_args={"bars": self.AUTOREGRESSION_LOOKBACK_BARS},
                            validate=False,
                        ),
                    ),
                    ("allocation", InverseVolatility()),
                ]
            ),
        )
