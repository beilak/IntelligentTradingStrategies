from typing import override

from its.strategies.core.optimization import EqualWeighted
from its.strategies.core.selectors import IntradayTurnoverSelector
from its.strategies.core.signals.pass_signals import KeepAllSignal
from its.strategies.core.types.strategy_types import Pipeline, Strategy, StrategyBuilder


class Generated2026050114191708e1ad5bTop3Builder(StrategyBuilder):
    """Materialized GA strategy generated at 2026-05-01T14:20:31.664683+00:00."""

    @override
    def build(self) -> Strategy:
        return Strategy(
            name='[GA][turnover_25m_20][pass_signal][equal_weighted]',
            description='GA materialized strategy. Selector=turnover_25m_20; Signal=pass_signal; Allocation=equal_weighted; TOTAL_SCORE=3.8413933532290443.',
            pipeline=Pipeline(
                steps=[
                    (
                        'pre_selection',
                        IntradayTurnoverSelector(
                            asset_universe_prices=self._asset_universe_prices,
                            lookback_bars=20,
                            min_turnover=25_000_000,
                            allow_empty_selection=False,
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
