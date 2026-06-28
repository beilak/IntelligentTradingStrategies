from typing import override

from sklearn.preprocessing import FunctionTransformer

from its.strategies.core.optimization import InverseVolatility
from its.strategies.core.selectors import IntradayTurnoverSelector
from its.strategies.core.signals import CamarillaSupportCrossSignal
from its.strategies.core.types.strategy_types import (Pipeline, Strategy,
                                                      StrategyBuilder)


def _recent_rows(values, *, bars: int):
    return values.iloc[-bars:] if hasattr(values, "iloc") else values[-bars:]


class ModelTurnoverCamarillaWithInverseVolatilityBuilder(StrategyBuilder):
    """Select liquid assets crossing a Camarilla support from below."""

    SUPPORT_LINE = "S1"
    CAMARILLA_MULTIPLIER = 1.1
    TURNOVER_LOOKBACK_BARS = 2
    MIN_TURNOVER_RUB = 1_000_000_000
    ALLOCATION_LOOKBACK_BARS = 60

    @override
    def build(self) -> Strategy:
        return Strategy(
            name="Turnover_camarilla_with_inverse_volatility",
            description=(
                f"Select liquid assets whose close crosses Camarilla "
                f"{self.SUPPORT_LINE} from below; allocate by inverse volatility "
                f"over the last {self.ALLOCATION_LOOKBACK_BARS} bars"
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
                        "camarilla_support_cross_signal",
                        CamarillaSupportCrossSignal(
                            support_line=self.SUPPORT_LINE,
                            camarilla_multiplier=self.CAMARILLA_MULTIPLIER,
                            asset_universe_prices=self._asset_universe_prices,
                        ),
                    ),
                    (
                        "allocation_window",
                        FunctionTransformer(
                            _recent_rows,
                            kw_args={"bars": self.ALLOCATION_LOOKBACK_BARS},
                            validate=False,
                        ),
                    ),
                    ("allocation", InverseVolatility()),
                ]
            ),
        )
