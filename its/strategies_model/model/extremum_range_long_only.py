from __future__ import annotations

from typing import override

from its.strategies.core.types.strategy_types import Strategy as CoreStrategy
from its.strategies.models.extremum_range_long_only import (
    ModelExtremumRangeLongOnlyBuilder,
)
from its.strategies_model.core.trading_strategy import (
    DonchianTrailingStopPolicy,
    PositionExitPolicy,
    PositionLifecycleConfig,
    TradingStrategyBuilder,
)


class ModelExtremumRangeLongOnlyTrailingStop10Builder(TradingStrategyBuilder):
    """Full long-only Extremum Range strategy with a rebalance-refreshed T10."""

    TRAIL_LOOKBACK_BARS = 10
    ALLOCATION_PCT = ModelExtremumRangeLongOnlyBuilder.ALLOCATION_PCT
    UNIVERSE_SELECTOR_STEP = "quarterly_turnover_pre_selection"

    @property
    @override
    def name(self) -> str:
        return "ExtremumRangeLongOnly_T10"

    @property
    @override
    def description(self) -> str:
        return (
            "Uses the frozen FAST long-only Extremum Range core for new entries; "
            "holds positions without repeated breakouts, allocates 70% equally, "
            "and exits on a rebalance-refreshed 10-bar lowest-low trailing stop "
            "or quarterly universe removal."
        )

    @override
    def build_core_strategy(self) -> CoreStrategy:
        return ModelExtremumRangeLongOnlyBuilder(
            self._asset_universe_prices,
            self._assets_info,
            self._runtime_context,
        ).build()

    @override
    def build_exit_policy(self) -> PositionExitPolicy:
        return DonchianTrailingStopPolicy(trail_lookback_bars=self.TRAIL_LOOKBACK_BARS)

    @override
    def build_position_lifecycle(self) -> PositionLifecycleConfig:
        return PositionLifecycleConfig(
            mode="hold_until_exit",
            allocation_pct=self.ALLOCATION_PCT,
            universe_selector_step=self.UNIVERSE_SELECTOR_STEP,
            close_on_universe_removal=True,
        )

    @override
    def build_supports_live_execution(self) -> bool:
        return False

    @override
    def build_metadata(self) -> dict[str, object]:
        return {
            "core_builder": "ModelExtremumRangeLongOnlyBuilder",
            "trail_lookback_bars": self.TRAIL_LOOKBACK_BARS,
            "allocation_pct": self.ALLOCATION_PCT,
            "entry_trigger": "rebalance_close",
            "stop_refresh": "rebalance",
            "take_profit": None,
        }
