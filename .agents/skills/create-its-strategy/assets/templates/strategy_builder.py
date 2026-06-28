from typing import override

from its.strategies.core.optimization import InverseVolatility
from its.strategies.core.selectors import ExampleSelector
from its.strategies.core.signals import ExampleSignal
from its.strategies.core.types.strategy_types import Pipeline, Strategy, StrategyBuilder


class ExampleStrategyBuilder(StrategyBuilder):
    LOOKBACK_BARS = 20

    @override
    def build(self) -> Strategy:
        return Strategy(
            name="example_strategy",
            description="TODO: explain selection and allocation rules",
            pipeline=Pipeline(
                steps=[
                    ("pre_selection", ExampleSelector()),
                    (
                        "signal",
                        ExampleSignal(
                            lookback_bars=self.LOOKBACK_BARS,
                            asset_universe_prices=self._asset_universe_prices,
                        ),
                    ),
                    ("allocation", InverseVolatility()),
                ]
            ),
        )

