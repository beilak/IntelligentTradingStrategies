from typing import override

from its.strategies.core.optimization import HierarchicalRiskParity
from its.strategies.core.selectors import SectorSelector
from its.strategies.core.signals.pass_signals import KeepAllSignal
from its.strategies.core.types.strategy_types import Pipeline, Strategy, StrategyBuilder


class Generated20260501135217332887deTop3Builder(StrategyBuilder):
    """Materialized GA strategy generated at 2026-05-01T13:52:20.931634+00:00."""

    @override
    def build(self) -> Strategy:
        return Strategy(
            name='[GA][sector_energy][pass_signal][HierarchicalRiskParity]',
            description='GA materialized strategy. Selector=sector_energy; Signal=pass_signal; Allocation=HierarchicalRiskParity; TOTAL_SCORE=0.0.',
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
                        HierarchicalRiskParity(
                            raise_on_failure=False,
                        )
                    )
                ]
            ),
        )
