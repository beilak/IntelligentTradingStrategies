from typing import override

from its.strategies.core.optimization import InverseVolatility
from its.strategies.core.selectors import IntradayTurnoverSelector
from its.strategies.core.selectors import SafeEmptySelector
from its.strategies.core.selectors import TrendSelector
from its.strategies.core.types.strategy_types import Pipeline, Strategy, StrategyBuilder


class Generated202604292048197c4a3d93Top1Builder(StrategyBuilder):
    """Materialized GA strategy generated at 2026-04-29T20:48:29.409316+00:00."""

    @override
    def build(self) -> Strategy:
        return Strategy(
            name='[GA][turnover_1m_10][trend_20][inverse_volatility]',
            description='GA materialized strategy. Selector=turnover_1m_10; Signal=trend_20; Allocation=inverse_volatility; TOTAL_SCORE=15.97187485966738.',
            pipeline=Pipeline(
                steps=[
                    (
                        'ga_pre_selection',
                        IntradayTurnoverSelector(
                            asset_universe_prices=self._asset_universe_prices,
                            lookback_bars=10,
                            min_turnover=1_000_000,
                            allow_empty_selection=False,
                        )
                    ),
                    (
                        'ga_signal',
                        SafeEmptySelector(
                            TrendSelector(
                                window=20,
                            ),
                        )
                    ),
                    (
                        'ga_allocation',
                        InverseVolatility(
                            raise_on_failure=False,
                        )
                    )
                ]
            ),
        )
