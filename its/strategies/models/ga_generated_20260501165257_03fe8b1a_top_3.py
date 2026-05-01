from typing import override

from its.strategies.core.optimization import InverseVolatility
from its.strategies.core.selectors import SafeEmptySelector
from its.strategies.core.selectors import SectorSelector
from its.strategies.core.signals.two_candle_trend_signal import TwoCandlePositiveTrendSignal
from its.strategies.core.types.strategy_types import Pipeline, Strategy, StrategyBuilder


class Generated2026050116525703fe8b1aTop3Builder(StrategyBuilder):
    """Materialized GA strategy generated at 2026-05-01T16:53:09.377897+00:00."""

    @override
    def build(self) -> Strategy:
        return Strategy(
            name='[GA][sector_it_telecom][TwoCandlePositiveTrendSignal][inverse_volatility]',
            description='GA materialized strategy. Selector=sector_it_telecom; Signal=TwoCandlePositiveTrendSignal; Allocation=inverse_volatility; TOTAL_SCORE=23.505162070196093.',
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
                        InverseVolatility(
                            raise_on_failure=False,
                        )
                    )
                ]
            ),
        )
