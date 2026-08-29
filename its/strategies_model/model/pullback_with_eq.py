from __future__ import annotations

from typing import override

from its.strategies.core.types.strategy_types import Strategy as CoreStrategy
from its.strategies.models.ticker_pullback_eq import ModelPullbackWithEQBuilder
from its.strategies_model.core.trading_strategy import (
    FixedStopTakeProfitPolicy,
    PositionExitPolicy,
    TradingStrategyBuilder,
)


class ModelPullbackWithEqStopLoss1TakeProfit3Builder(TradingStrategyBuilder):
    """Trading strategy: ModelPullbackWithEQBuilder core, 1% stop loss, 3% take profit."""

    STOP_LOSS_PCT = 0.01
    TAKE_PROFIT_PCT = 0.03

    @property
    @override
    def name(self) -> str:
        return "ModelPullbackWithEQBuilder_SL1_TP3"

    @property
    @override
    def description(self) -> str:
        return (
            "Uses ModelPullbackWithEQBuilder as the portfolio core and closes "
            "each security at 1% stop loss or 3% take profit before the next rebalance."
        )

    @override
    def build_core_strategy(self) -> CoreStrategy:
        return ModelPullbackWithEQBuilder(
            self._asset_universe_prices,
            self._assets_info,
            self._runtime_context,
        ).build()

    @override
    def build_exit_policy(self) -> PositionExitPolicy:
        return FixedStopTakeProfitPolicy(
            stop_loss_pct=self.STOP_LOSS_PCT,
            take_profit_pct=self.TAKE_PROFIT_PCT,
        )

    @override
    def build_metadata(self) -> dict[str, object]:
        return {
            "core_builder": "ModelPullbackWithEQBuilder",
            "stop_loss_pct": self.STOP_LOSS_PCT,
            "take_profit_pct": self.TAKE_PROFIT_PCT,
        }
