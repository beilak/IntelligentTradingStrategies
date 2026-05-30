from typing import override

from its.strategies.core.optimization import EqualWeighted
from its.strategies.core.selectors import IntradayTurnoverSelector
from its.strategies.core.signals.two_candle_trend_signal import TwoCandlePositiveTrendSignal
from its.strategies.core.types.strategy_types import Pipeline, Strategy, StrategyBuilder


class Generated20260501135256B344014dTop3Builder(StrategyBuilder):
    """Materialized GA strategy generated at 2026-05-01T13:52:59.766799+00:00."""

    @override
    def build(self) -> Strategy:
        return Strategy(
            name='[GA][turnover_25m_20][TwoCandlePositiveTrendSignal][equal_weighted]',
            description='GA materialized strategy. Selector=turnover_25m_20; Signal=TwoCandlePositiveTrendSignal; Allocation=equal_weighted; TOTAL_SCORE=0.0.',
            pipeline=Pipeline(
                steps=[
                    (
                        'pre_selection',
                        IntradayTurnoverSelector(
                            asset_universe_prices=self._asset_universe_prices,
                            lookback_bars=20,
                            min_turnover=25_000_000,
                            allow_empty_selection=False,
                        )
                    ),
                    (
                        'signal',
                        TwoCandlePositiveTrendSignal()
                    ),
                    (
                        'allocation',
                        EqualWeighted()
                    )
                ]
            ),
        )
