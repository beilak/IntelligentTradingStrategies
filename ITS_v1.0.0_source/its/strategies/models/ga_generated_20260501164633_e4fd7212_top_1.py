from typing import override

from its.strategies.core.optimization import EqualWeighted
from its.strategies.core.selectors import SafeEmptySelector
from its.strategies.core.selectors import SectorSelector
from its.strategies.core.signals.two_candle_trend_signal import TwoCandlePositiveTrendSignal
from its.strategies.core.types.strategy_types import Pipeline, Strategy, StrategyBuilder


class Generated20260501164633E4fd7212Top1Builder(StrategyBuilder):
    """Materialized GA strategy generated at 2026-05-01T16:46:59.370278+00:00."""

    @override
    def build(self) -> Strategy:
        return Strategy(
            name='[GA][sector_it_telecom][TwoCandlePositiveTrendSignal][equal_weighted]',
            description='GA materialized strategy. Selector=sector_it_telecom; Signal=TwoCandlePositiveTrendSignal; Allocation=equal_weighted; TOTAL_SCORE=23.505162070196093.',
            pipeline=Pipeline(
                steps=[
                    (
                        'pre_selection',
                        SafeEmptySelector(
                            SectorSelector(
                                assets_info=self._assets_info,
                                sectors=['it', 'telecom'],
                            ),
                        )
                    ),
                    (
                        'signal',
                        SafeEmptySelector(
                            TwoCandlePositiveTrendSignal(),
                        )
                    ),
                    (
                        'allocation',
                        EqualWeighted()
                    )
                ]
            ),
        )
