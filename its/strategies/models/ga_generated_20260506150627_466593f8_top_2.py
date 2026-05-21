from typing import override

from its.strategies.core.optimization import InverseVolatility
from its.strategies.core.selectors import DividendHistorySelector
from its.strategies.core.selectors import SafeEmptySelector
from its.strategies.core.signals.pass_signals import KeepAllSignal
from its.strategies.core.types.strategy_types import Pipeline, Strategy, StrategyBuilder


class Generated20260506150627466593f8Top2Builder(StrategyBuilder):
    """Materialized GA strategy generated at 2026-05-06T15:07:25.466149+00:00."""

    @override
    def build(self) -> Strategy:
        return Strategy(
            name='[GA][DividendHistorySelector][pass_signal][inverse_volatility]',
            description='GA materialized strategy. Selector=DividendHistorySelector; Signal=pass_signal; Allocation=inverse_volatility; TOTAL_SCORE=22.601570488215714.',
            pipeline=Pipeline(
                steps=[
                    (
                        'pre_selection',
                        SafeEmptySelector(
                            DividendHistorySelector(
                                dividends_df=self._dividends_info,
                                years=3,
                            ),
                        )
                    ),
                    (
                        'signal',
                        KeepAllSignal()
                    ),
                    (
                        'allocation',
                        InverseVolatility(
                            raise_on_failure=False,
                        )
                    )
                ]
            ),
        )
