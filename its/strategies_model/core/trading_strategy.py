from __future__ import annotations

import abc
import dataclasses
import math
import typing as tp

import pandas as pd

from its.strategies.core.types.strategy_types import Strategy as CoreStrategy

PositionLifecycleMode = tp.Literal["rebalance_target", "hold_until_exit"]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class PositionLifecycleConfig:
    """Describe how core rebalance output controls open positions."""

    mode: PositionLifecycleMode = "rebalance_target"
    allocation_pct: float | None = None
    universe_selector_step: str | None = None
    close_on_universe_removal: bool = False

    def __post_init__(self) -> None:
        if self.mode not in {"rebalance_target", "hold_until_exit"}:
            raise ValueError(
                "mode must be either 'rebalance_target' or 'hold_until_exit'."
            )
        if self.allocation_pct is not None and (
            not math.isfinite(self.allocation_pct) or not 0 <= self.allocation_pct <= 1
        ):
            raise ValueError("allocation_pct must be in the interval [0, 1].")
        if self.mode == "hold_until_exit" and self.allocation_pct is None:
            raise ValueError(
                "allocation_pct is required when mode is 'hold_until_exit'."
            )
        if self.close_on_universe_removal and not self.universe_selector_step:
            raise ValueError(
                "universe_selector_step is required when "
                "close_on_universe_removal is enabled."
            )


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class PositionContext:
    """Market context for one open position at one bar."""

    ticker: str
    entry_time: pd.Timestamp
    current_time: pd.Timestamp
    entry_price: float
    current_price: float
    weight: float
    open_price: float | None = None
    high_price: float | None = None
    low_price: float | None = None
    active_stop_price: float | None = None
    closed_low_history: tuple[float, ...] = ()
    metadata: tp.Mapping[str, tp.Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class PositionExitDecision:
    """Decision to close a position before the next core rebalance."""

    reason: str
    execution_price: float
    threshold_price: float
    return_pct: float


@tp.runtime_checkable
class PositionExitPolicy(tp.Protocol):
    """Protocol for stop loss, take profit, and other position exits."""

    @property
    def name(self) -> str: ...

    @property
    def description(self) -> str: ...

    def evaluate(self, context: PositionContext) -> PositionExitDecision | None:
        """Return a close-position decision or None to keep holding."""


@tp.runtime_checkable
class RebalanceAwareExitPolicy(PositionExitPolicy, tp.Protocol):
    """Exit policy that refreshes a persisted stop after each rebalance."""

    @property
    def required_history_bars(self) -> int: ...

    def refresh_stop(
        self,
        context: PositionContext,
        previous_stop: float | None,
    ) -> float | None:
        """Return the stop that becomes active after the rebalance bar."""


class HoldToRebalancePolicy:
    """Default policy: positions are only changed by the core rebalance schedule."""

    @property
    def name(self) -> str:
        return "hold_to_rebalance"

    @property
    def description(self) -> str:
        return "No stop loss or take profit. Hold positions until the next rebalance."

    def evaluate(self, context: PositionContext) -> PositionExitDecision | None:
        return None


class FixedStopTakeProfitPolicy:
    """Close each position by fixed stop loss and take profit percentages.

    Modelers can use this as-is or write their own PositionExitPolicy with the
    same evaluate(context) hook.
    """

    def __init__(
        self,
        *,
        stop_loss_pct: float | None = None,
        take_profit_pct: float | None = None,
        conservative_same_bar: bool = True,
    ) -> None:
        if stop_loss_pct is not None and stop_loss_pct < 0:
            raise ValueError("stop_loss_pct must be greater than or equal to 0.")
        if take_profit_pct is not None and take_profit_pct < 0:
            raise ValueError("take_profit_pct must be greater than or equal to 0.")

        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.conservative_same_bar = conservative_same_bar

    @property
    def name(self) -> str:
        return "fixed_stop_take_profit"

    @property
    def description(self) -> str:
        stop = format_pct(self.stop_loss_pct)
        take = format_pct(self.take_profit_pct)
        return f"Fixed stop loss {stop}; fixed take profit {take} per security."

    def evaluate(self, context: PositionContext) -> PositionExitDecision | None:
        if not is_finite_positive(context.entry_price):
            return None

        current_price = context.current_price
        if not is_finite_positive(current_price):
            return None

        low_price = (
            context.low_price
            if is_finite_positive(context.low_price)
            else current_price
        )
        high_price = (
            context.high_price
            if is_finite_positive(context.high_price)
            else current_price
        )

        stop_decision = self._stop_loss_decision(context, low_price)
        take_decision = self._take_profit_decision(context, high_price)

        if stop_decision and take_decision:
            return stop_decision if self.conservative_same_bar else take_decision
        return stop_decision or take_decision

    def _stop_loss_decision(
        self,
        context: PositionContext,
        low_price: float,
    ) -> PositionExitDecision | None:
        if not self.stop_loss_pct:
            return None

        threshold = context.entry_price * (1 - self.stop_loss_pct)
        if low_price > threshold:
            return None

        return PositionExitDecision(
            reason="stop_loss",
            execution_price=threshold,
            threshold_price=threshold,
            return_pct=threshold / context.entry_price - 1,
        )

    def _take_profit_decision(
        self,
        context: PositionContext,
        high_price: float,
    ) -> PositionExitDecision | None:
        if not self.take_profit_pct:
            return None

        threshold = context.entry_price * (1 + self.take_profit_pct)
        if high_price < threshold:
            return None

        return PositionExitDecision(
            reason="take_profit",
            execution_price=threshold,
            threshold_price=threshold,
            return_pct=threshold / context.entry_price - 1,
        )


class DonchianTrailingStopPolicy:
    """Long-only rolling lowest-low stop refreshed at rebalances."""

    def __init__(self, *, trail_lookback_bars: int = 10) -> None:
        if trail_lookback_bars <= 0:
            raise ValueError("trail_lookback_bars must be positive.")
        self.trail_lookback_bars = trail_lookback_bars

    @property
    def name(self) -> str:
        return "donchian_trailing_stop"

    @property
    def description(self) -> str:
        return (
            "Long-only trailing stop at the lowest low of the previous "
            f"{self.trail_lookback_bars} completed bars, refreshed at rebalances."
        )

    @property
    def required_history_bars(self) -> int:
        return self.trail_lookback_bars

    def refresh_stop(
        self,
        context: PositionContext,
        previous_stop: float | None,
    ) -> float | None:
        history = context.closed_low_history[-self.trail_lookback_bars :]
        if len(history) < self.trail_lookback_bars:
            return previous_stop if is_finite_positive(previous_stop) else None
        if not all(is_finite_positive(value) for value in history):
            return previous_stop if is_finite_positive(previous_stop) else None

        candidate = min(history)
        if is_finite_positive(previous_stop):
            return max(float(previous_stop), candidate)
        return candidate

    def evaluate(self, context: PositionContext) -> PositionExitDecision | None:
        stop = context.active_stop_price
        if not is_finite_positive(stop) or not is_finite_positive(context.entry_price):
            return None

        current_price = context.current_price
        if not is_finite_positive(current_price):
            return None
        low_price = (
            context.low_price
            if is_finite_positive(context.low_price)
            else current_price
        )
        if low_price > stop:
            return None

        execution_price = float(stop)
        if is_finite_positive(context.open_price) and context.open_price < stop:
            execution_price = float(context.open_price)
        return PositionExitDecision(
            reason="trailing_stop",
            execution_price=execution_price,
            threshold_price=float(stop),
            return_pct=execution_price / context.entry_price - 1,
        )


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class TradingStrategy:
    """Full trading strategy: core portfolio model plus trade-management logic."""

    name: str
    description: str
    core: CoreStrategy
    exit_policy: PositionExitPolicy = dataclasses.field(
        default_factory=HoldToRebalancePolicy
    )
    position_lifecycle: PositionLifecycleConfig = dataclasses.field(
        default_factory=PositionLifecycleConfig
    )
    supports_live_execution: bool = True
    metadata: tp.Mapping[str, tp.Any] = dataclasses.field(default_factory=dict)

    def evaluate_position(
        self, context: PositionContext
    ) -> PositionExitDecision | None:
        return self.exit_policy.evaluate(context)

    def refresh_position_stop(
        self,
        context: PositionContext,
        previous_stop: float | None,
    ) -> float | None:
        if isinstance(self.exit_policy, RebalanceAwareExitPolicy):
            return self.exit_policy.refresh_stop(context, previous_stop)
        return previous_stop


@tp.runtime_checkable
class TradingStrategyProtocol(tp.Protocol):
    """Runtime protocol consumed by strategy backtests."""

    name: str
    description: str
    core: CoreStrategy
    exit_policy: PositionExitPolicy
    position_lifecycle: PositionLifecycleConfig
    supports_live_execution: bool

    def evaluate_position(
        self, context: PositionContext
    ) -> PositionExitDecision | None: ...

    def refresh_position_stop(
        self,
        context: PositionContext,
        previous_stop: float | None,
    ) -> float | None: ...


class TradingStrategyBuilder(abc.ABC):
    """Base class for modelers creating full trading strategies.

    Override build_core_strategy() to choose the portfolio core and override
    build_exit_policy() to add stop loss, take profit, or custom exit logic.
    """

    def __init__(
        self,
        _asset_universe_prices: pd.DataFrame,
        _assets_info: pd.DataFrame | None = None,
        _runtime_context: dict[str, tp.Any] | None = None,
        _dividends_info: pd.DataFrame | None = None,
    ) -> None:
        self._asset_universe_prices = _asset_universe_prices
        self._assets_info = _assets_info
        self._runtime_context = _runtime_context or {}
        self._dividends_info = _dividends_info

    @property
    @abc.abstractmethod
    def name(self) -> str: ...

    @property
    @abc.abstractmethod
    def description(self) -> str: ...

    @abc.abstractmethod
    def build_core_strategy(self) -> CoreStrategy:
        """Build the portfolio-allocation core used for rebalances."""

    def build_exit_policy(self) -> PositionExitPolicy:
        """Build trade-management logic. Override this for stop/take rules."""
        return HoldToRebalancePolicy()

    def build_position_lifecycle(self) -> PositionLifecycleConfig:
        """Build how core targets interact with positions between rebalances."""
        return PositionLifecycleConfig()

    def build_supports_live_execution(self) -> bool:
        """Return whether the live runner can safely execute this strategy."""
        return True

    def build_metadata(self) -> dict[str, tp.Any]:
        return {}

    def build(self) -> TradingStrategy:
        return TradingStrategy(
            name=self.name,
            description=self.description,
            core=self.build_core_strategy(),
            exit_policy=self.build_exit_policy(),
            position_lifecycle=self.build_position_lifecycle(),
            supports_live_execution=self.build_supports_live_execution(),
            metadata=self.build_metadata(),
        )


def is_finite_positive(value: float | None) -> bool:
    return value is not None and math.isfinite(value) and value > 0


def format_pct(value: float | None) -> str:
    if value is None:
        return "disabled"
    return f"{value:.2%}"
