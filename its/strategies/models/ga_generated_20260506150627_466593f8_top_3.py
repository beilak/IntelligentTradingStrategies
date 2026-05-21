from typing import override

from its.strategies.core.optimization import InverseVolatility
from its.strategies.core.selectors import DividendHistorySelector
from its.strategies.core.selectors import SafeEmptySelector
from its.strategies.core.signals.price_breakout_signal import PriceBreakoutSignal
from its.strategies.core.types.strategy_types import Pipeline, Strategy, StrategyBuilder


class Generated20260506150627466593f8Top3Builder(StrategyBuilder):
    """Materialized GA strategy generated at 2026-05-06T15:07:25.471759+00:00."""

    @override
    def build(self) -> Strategy:
        return Strategy(
            name='[GA][DividendHistorySelector][PriceBreakoutSignal][inverse_volatility]',
            description='GA materialized strategy. Selector=DividendHistorySelector; Signal=PriceBreakoutSignal; Allocation=inverse_volatility; TOTAL_SCORE=22.332844929464713.',
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
                        SafeEmptySelector(
                            PriceBreakoutSignal(),
                        )
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
