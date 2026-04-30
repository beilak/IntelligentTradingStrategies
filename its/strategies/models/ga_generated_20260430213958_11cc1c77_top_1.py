from typing import override

from its.strategies.core.optimization import InverseVolatility
from its.strategies.core.selectors import SectorSelector
from its.strategies.core.signals.pass_signals import KeepAllSignal
from its.strategies.core.types.strategy_types import Pipeline, Strategy, StrategyBuilder


class Generated2026043021395811cc1c77Top1Builder(StrategyBuilder):
    """Materialized GA strategy generated at 2026-04-30T21:40:22.064530+00:00."""

    @override
    def build(self) -> Strategy:
        return Strategy(
            name='[GA][sector_energy][pass_signal][inverse_volatility]',
            description='GA materialized strategy. Selector=sector_energy; Signal=pass_signal; Allocation=inverse_volatility; TOTAL_SCORE=19.695202387523338.',
            pipeline=Pipeline(
                steps=[
                    (
                        'pre_selection',
                        SectorSelector(
                            assets_info=self._assets_info,
                            sectors=['energy', 'telecom'],
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
