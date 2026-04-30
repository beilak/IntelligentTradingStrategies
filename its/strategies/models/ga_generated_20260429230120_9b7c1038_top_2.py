from typing import override

from its.strategies.core.optimization import EqualWeighted
from its.strategies.core.selectors import SectorSelector
from its.strategies.core.signals.pass_signals import KeepAllSignal
from its.strategies.core.types.strategy_types import Pipeline, Strategy, StrategyBuilder


class Generated202604292301209b7c1038Top2Builder(StrategyBuilder):
    """Materialized GA strategy generated at 2026-04-29T23:01:24.660630+00:00."""

    @override
    def build(self) -> Strategy:
        return Strategy(
            name='[GA][sector_it_telecom][pass_signal][equal_weighted]',
            description='GA materialized strategy. Selector=sector_it_telecom; Signal=pass_signal; Allocation=equal_weighted; TOTAL_SCORE=9.290375382391183.',
            pipeline=Pipeline(
                steps=[
                    (
                        'pre_selection',
                        SectorSelector(
                            assets_info=self._assets_info,
                            sectors=['it', 'telecom'],
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
