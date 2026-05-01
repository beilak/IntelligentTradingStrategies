from __future__ import annotations

import abc
import dataclasses
import math
import typing as tp

import pandas as pd

from its.strategies.core.types.strategy_types import Strategy as CoreStrategy


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class PositionContext:
    """Market context for one open position at one bar."""

    ticker: str
    entry_time: pd.Timestamp
    current_time: pd.Timestamp
    entry_price: float
    current_price: float
    weight: float
    high_price: float | None = None
    low_price: float | None = None
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

        low_price = context.low_price if is_finite_positive(context.low_price) else current_price
        high_price = context.high_price if is_finite_positive(context.high_price) else current_price

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


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class TradingStrategy:
    """Full trading strategy: core portfolio model plus trade-management logic."""

    name: str
    description: str
    core: CoreStrategy
    exit_policy: PositionExitPolicy = dataclasses.field(default_factory=HoldToRebalancePolicy)
    metadata: tp.Mapping[str, tp.Any] = dataclasses.field(default_factory=dict)

    def evaluate_position(self, context: PositionContext) -> PositionExitDecision | None:
        return self.exit_policy.evaluate(context)


@tp.runtime_checkable
class TradingStrategyProtocol(tp.Protocol):
    """Runtime protocol consumed by strategy backtests."""

    name: str
    description: str
    core: CoreStrategy
    exit_policy: PositionExitPolicy

    def evaluate_position(self, context: PositionContext) -> PositionExitDecision | None: ...


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
    ) -> None:
        self._asset_universe_prices = _asset_universe_prices
        self._assets_info = _assets_info
        self._runtime_context = _runtime_context or {}

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

    def build_metadata(self) -> dict[str, tp.Any]:
        return {}

    def build(self) -> TradingStrategy:
        return TradingStrategy(
            name=self.name,
            description=self.description,
            core=self.build_core_strategy(),
            exit_policy=self.build_exit_policy(),
            metadata=self.build_metadata(),
        )


def is_finite_positive(value: float | None) -> bool:
    return value is not None and math.isfinite(value) and value > 0


def format_pct(value: float | None) -> str:
    if value is None:
        return "disabled"
    return f"{value:.2%}"
