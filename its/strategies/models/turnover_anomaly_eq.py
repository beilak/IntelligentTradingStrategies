from typing import override

from its.strategies.core.optimization import EqualWeighted, InverseVolatility
from its.strategies.core.selectors import IntradayTurnoverSelector
from its.strategies.core.signals import PyODAnomalySignal
from its.strategies.core.types.strategy_types import Pipeline, Strategy, StrategyBuilder


class _TurnoverAnomalyStrategyBase(StrategyBuilder):
    """Shared configuration for turnover-filtered anomaly strategies."""

    DIRECTION = "positive"
    LOOKBACK_BARS = 60
    TURNOVER_LOOKBACK_BARS = 2
    MIN_TURNOVER_RUB = 1_000_000_000

    def _build_pipeline(self, allocation) -> Pipeline:
        return Pipeline(
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
                    "anomaly_signal",
                    PyODAnomalySignal(
                        lookback_bars=self.LOOKBACK_BARS,
                        direction=self.DIRECTION,
                        asset_universe_prices=self._asset_universe_prices,
                    ),
                ),
                ("allocation", allocation),
            ]
        )


class ModelTurnoverAnomalyWithEQBuilder(_TurnoverAnomalyStrategyBase):
    """Select liquid assets with a positive PyOD anomaly; allocate equally."""

    @override
    def build(self) -> Strategy:
        return Strategy(
            name="Turnover_anomaly_with_EQ",
            description=(
                "Select liquid assets whose latest bar is a positive anomaly "
                f"detected by PyOD over {self.LOOKBACK_BARS} bars; "
                "allocate Equal Weighted"
            ),
            pipeline=self._build_pipeline(EqualWeighted()),
        )


class ModelTurnoverAnomalyWithInverseVolatilityBuilder(_TurnoverAnomalyStrategyBase):
    """Select liquid assets with a positive PyOD anomaly; allocate inverse vol."""

    @override
    def build(self) -> Strategy:
        return Strategy(
            name="Turnover_anomaly_with_inverse_volatility",
            description=(
                "Select liquid assets whose latest bar is a positive anomaly "
                f"detected by PyOD over {self.LOOKBACK_BARS} bars; "
                "allocate by inverse volatility"
            ),
            pipeline=self._build_pipeline(InverseVolatility()),
        )