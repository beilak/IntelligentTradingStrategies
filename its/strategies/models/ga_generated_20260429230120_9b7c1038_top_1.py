from typing import override

from its.strategies.core.optimization import EqualWeighted
from its.strategies.core.selectors import IntradayTurnoverSelector
from its.strategies.core.signals.pass_signals import KeepAllSignal
from its.strategies.core.types.strategy_types import Pipeline, Strategy, StrategyBuilder


class Generated202604292301209b7c1038Top1Builder(StrategyBuilder):
    """Materialized GA strategy generated at 2026-04-29T23:01:24.655400+00:00."""

    @override
    def build(self) -> Strategy:
        return Strategy(
            name='[GA][turnover_25m_20][pass_signal][equal_weighted]',
            description='GA materialized strategy. Selector=turnover_25m_20; Signal=pass_signal; Allocation=equal_weighted; TOTAL_SCORE=10.351508771092924.',
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
