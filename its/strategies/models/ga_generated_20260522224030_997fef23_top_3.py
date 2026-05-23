from typing import override

from its.strategies.core.optimization import EqualWeighted
from its.strategies.core.selectors import IntradayTurnoverSelector
from its.strategies.core.selectors import SafeEmptySelector
from its.strategies.core.signals.pass_signals import KeepAllSignal
from its.strategies.core.types.strategy_types import Pipeline, Strategy, StrategyBuilder


class Generated20260522224030997fef23Top3Builder(StrategyBuilder):
    """Materialized GA strategy generated at 2026-05-22T22:41:37.842314+00:00."""

    @override
    def build(self) -> Strategy:
        return Strategy(
            name='[GA][turnover_1m_10][pass_signal][equal_weighted]',
            description='GA materialized strategy. Selector=turnover_1m_10; Signal=pass_signal; Allocation=equal_weighted; TOTAL_SCORE=19.11475864791865.',
            pipeline=Pipeline(
                steps=[
                    (
                        'pre_selection',
                        SafeEmptySelector(
                            IntradayTurnoverSelector(
                                asset_universe_prices=self._asset_universe_prices,
                                lookback_bars=10,
                                min_turnover=1_000_000,
                                allow_empty_selection=False,
                            ),
                        )
                    ),
                    (
                        'signal',
                        KeepAllSignal()
                    ),
                    (
                        'allocation',
                        EqualWeighted()
                    )
                ]
            ),
        )
