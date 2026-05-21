from typing import override

from its.strategies.core.optimization import CVaR
from its.strategies.core.selectors import DividendHistorySelector
from its.strategies.core.selectors import SafeEmptySelector
from its.strategies.core.signals.pass_signals import KeepAllSignal
from its.strategies.core.types.strategy_types import Pipeline, Strategy, StrategyBuilder


class Generated20260506150627466593f8Top1Builder(StrategyBuilder):
    """Materialized GA strategy generated at 2026-05-06T15:07:25.458230+00:00."""

    @override
    def build(self) -> Strategy:
        return Strategy(
            name='[GA][DividendHistorySelector][pass_signal][CVaR]',
            description='GA materialized strategy. Selector=DividendHistorySelector; Signal=pass_signal; Allocation=CVaR; TOTAL_SCORE=23.141550346834308.',
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
                        CVaR(
                            beta=0.95,
                        )
                    )
                ]
            ),
        )
