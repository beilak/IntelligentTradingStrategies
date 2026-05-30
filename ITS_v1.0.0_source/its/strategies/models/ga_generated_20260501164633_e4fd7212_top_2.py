from typing import override

from its.strategies.core.optimization import CVaR
from its.strategies.core.selectors import SafeEmptySelector
from its.strategies.core.selectors import SectorSelector
from its.strategies.core.signals.two_candle_trend_signal import TwoCandlePositiveTrendSignal
from its.strategies.core.types.strategy_types import Pipeline, Strategy, StrategyBuilder


class Generated20260501164633E4fd7212Top2Builder(StrategyBuilder):
    """Materialized GA strategy generated at 2026-05-01T16:46:59.377030+00:00."""

    @override
    def build(self) -> Strategy:
        return Strategy(
            name='[GA][sector_energy_telecom][TwoCandlePositiveTrendSignal][CVaR]',
            description='GA materialized strategy. Selector=sector_energy_telecom; Signal=TwoCandlePositiveTrendSignal; Allocation=CVaR; TOTAL_SCORE=23.439525556713164.',
            pipeline=Pipeline(
                steps=[
                    (
                        'pre_selection',
                        SafeEmptySelector(
                            SectorSelector(
                                assets_info=self._assets_info,
                                sectors=['energy', 'telecom'],
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
