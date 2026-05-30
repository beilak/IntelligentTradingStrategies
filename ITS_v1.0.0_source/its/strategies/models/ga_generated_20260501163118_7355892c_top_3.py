from typing import override

from its.strategies.core.optimization import CVaR
from its.strategies.core.selectors import SafeEmptySelector
from its.strategies.core.selectors import SectorSelector
from its.strategies.core.signals.two_candle_trend_signal import TwoCandlePositiveTrendSignal
from its.strategies.core.types.strategy_types import Pipeline, Strategy, StrategyBuilder


class Generated202605011631187355892cTop3Builder(StrategyBuilder):
    """Materialized GA strategy generated at 2026-05-01T16:32:58.977215+00:00."""

    @override
    def build(self) -> Strategy:
        return Strategy(
            name='[GA][sector_it_telecom][TwoCandlePositiveTrendSignal][CVaR]',
            description='GA materialized strategy. Selector=sector_it_telecom; Signal=TwoCandlePositiveTrendSignal; Allocation=CVaR; TOTAL_SCORE=23.172158905412743.',
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
                        CVaR(
                            beta=0.95,
                        )
                    )
                ]
            ),
        )
