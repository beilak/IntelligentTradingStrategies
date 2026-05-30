from typing import override

from its.strategies.core.optimization import EqualWeighted
from its.strategies.core.selectors import IntradayTurnoverSelector
from its.strategies.core.signals.pass_signals import KeepAllSignal
from its.strategies.core.types.strategy_types import Pipeline, Strategy, StrategyBuilder


class Generated20260429213858C37a6b6dTop1Builder(StrategyBuilder):
    """Materialized GA strategy generated at 2026-04-29T21:39:04.475137+00:00."""

    @override
    def build(self) -> Strategy:
        return Strategy(
            name="[GA][turnover_1m_10][pass_signal][equal_weighted]",
            description="GA materialized strategy. Selector=turnover_1m_10; Signal=pass_signal; Allocation=equal_weighted; TOTAL_SCORE=13.099181021682575.",
            pipeline=Pipeline(
                steps=[
                    (
                        "pre_selection",
                        IntradayTurnoverSelector(
                            asset_universe_prices=self._asset_universe_prices,
                            lookback_bars=10,
                            min_turnover=1_000_000,
                            allow_empty_selection=False,
                        ),
                    ),
                    ("signal", KeepAllSignal()),
                    ("allocation", EqualWeighted()),
                ]
            ),
        )
