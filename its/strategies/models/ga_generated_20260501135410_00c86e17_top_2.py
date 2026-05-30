from typing import override

from its.strategies.core.optimization import EqualWeighted
from its.strategies.core.selectors import IntradayTurnoverSelector
from its.strategies.core.signals.price_breakout_signal import PriceBreakoutSignal
from its.strategies.core.types.strategy_types import Pipeline, Strategy, StrategyBuilder


class Generated2026050113541000c86e17Top2Builder(StrategyBuilder):
    """Materialized GA strategy generated at 2026-05-01T13:55:11.747276+00:00."""

    @override
    def build(self) -> Strategy:
        return Strategy(
            name='[GA][turnover_1m_10][PriceBreakoutSignal][equal_weighted]',
            description='GA materialized strategy. Selector=turnover_1m_10; Signal=PriceBreakoutSignal; Allocation=equal_weighted; TOTAL_SCORE=0.0.',
            pipeline=Pipeline(
                steps=[
                    (
                        'pre_selection',
                        IntradayTurnoverSelector(
                            asset_universe_prices=self._asset_universe_prices,
                            lookback_bars=10,
                            min_turnover=1_000_000,
                            allow_empty_selection=False,
                        )
                    ),
                    (
                        'signal',
                        PriceBreakoutSignal()
                    ),
                    (
                        'allocation',
                        EqualWeighted()
                    )
                ]
            ),
        )
