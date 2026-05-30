from typing import override

from its.strategies.core.optimization import EqualWeighted
from its.strategies.core.selectors import IntradayTurnoverSelector
from its.strategies.core.selectors import SafeEmptySelector, TrendSelector
from its.strategies.core.types.strategy_types import Pipeline, Strategy, StrategyBuilder


class GAGenerated2026042920142098586f71Top3Builder(StrategyBuilder):
    """Materialized GA strategy generated at 2026-04-29T20:14:48.696034+00:00."""

    TURNOVER_LOOKBACK_BARS = 10
    MIN_TURNOVER_RUB = 1_000_000
    SIGNAL_WINDOW = 20

    @override
    def build(self) -> Strategy:
        return Strategy(
            name='[GA][turnover_1m_10][trend_20][equal_weighted]',
            description='GA materialized strategy. Selector=turnover_1m_10; Signal=trend_20; Allocation=equal_weighted; TOTAL_SCORE=14.681466962101943.',
            pipeline=Pipeline(
                steps=[
                    (
                        'ga_pre_selection',
                        IntradayTurnoverSelector(
                            asset_universe_prices=self._asset_universe_prices,
                            lookback_bars=self.TURNOVER_LOOKBACK_BARS,
                            min_turnover=self.MIN_TURNOVER_RUB,
                            allow_empty_selection=False,
                        )
                    ),
                    (
                        'ga_signal',
                        SafeEmptySelector(TrendSelector(window=self.SIGNAL_WINDOW))
                    ),
                    (
                        'ga_allocation',
                        EqualWeighted()
                    )
                ]
            ),
        )
