from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from its.strategies.core.types.strategy_types import Strategy as CoreStrategy
from its.strategies.testing.backtest.core import load_registered_trading_strategy
from its.strategies.testing.backtest.vectorbt_backtest import (
    backtest_strategies_vectorbt,
)
from its.strategies_model.core import (
    DonchianTrailingStopPolicy,
    PositionContext,
    PositionLifecycleConfig,
    TradingStrategy,
)
from its.strategies_model.model import ModelExtremumRangeLongOnlyTrailingStop10Builder

UNIVERSE_STEP = "quarterly_turnover_pre_selection"


class ScriptedUniverseSelector:
    asset_names_: np.ndarray
    to_keep_: np.ndarray


class ScriptedPipeline:
    def __init__(
        self,
        *,
        signals: dict[int, dict[str, float]],
        remove_bbb_at: int = 16,
    ) -> None:
        self.signals = signals
        self.remove_bbb_at = remove_bbb_at
        self.selector = ScriptedUniverseSelector()
        self.steps = [(UNIVERSE_STEP, self.selector), ("allocation", object())]
        self.named_steps = {name: step for name, step in self.steps}
        self.observations = 0

    def fit(self, x_train: pd.DataFrame) -> ScriptedPipeline:
        self.observations = len(x_train)
        self.selector.asset_names_ = x_train.columns.to_numpy(dtype=str)
        self.selector.to_keep_ = np.asarray(
            [
                ticker != "BBB" or self.observations < self.remove_bbb_at
                for ticker in self.selector.asset_names_
            ],
            dtype=bool,
        )
        return self

    def predict(self, x_test: pd.DataFrame) -> SimpleNamespace:
        return SimpleNamespace(weights_dict=self.signals.get(self.observations, {}))


def position_context(**overrides: object) -> PositionContext:
    values: dict[str, object] = {
        "ticker": "AAA",
        "entry_time": pd.Timestamp("2024-01-01"),
        "current_time": pd.Timestamp("2024-01-02"),
        "entry_price": 100.0,
        "current_price": 101.0,
        "weight": 0.7,
    }
    values.update(overrides)
    return PositionContext(**values)


def build_managed_strategy(
    *, signals: dict[int, dict[str, float]] | None = None
) -> TradingStrategy:
    pipeline = ScriptedPipeline(signals=signals or {10: {"AAA": 0.7}, 12: {"BBB": 0.7}})
    return TradingStrategy(
        name="scripted_extremum_range",
        description="Scripted hold-until-exit strategy.",
        core=CoreStrategy(
            name="scripted_core",
            description="Scripted entry candidates.",
            pipeline=pipeline,
        ),
        exit_policy=DonchianTrailingStopPolicy(trail_lookback_bars=10),
        position_lifecycle=PositionLifecycleConfig(
            mode="hold_until_exit",
            allocation_pct=0.70,
            universe_selector_step=UNIVERSE_STEP,
            close_on_universe_removal=True,
        ),
    )


def lifecycle_prices(periods: int = 20) -> tuple[pd.DataFrame, ...]:
    dates = pd.date_range("2024-01-01", periods=periods, freq="D")
    close = pd.DataFrame({"AAA": 100.0, "BBB": 200.0}, index=dates)
    open_prices = close.copy()
    high = pd.DataFrame({"AAA": 101.0, "BBB": 201.0}, index=dates)
    low = pd.DataFrame({"AAA": 95.0, "BBB": 190.0}, index=dates)
    low.loc[dates[10:13], "AAA"] = 96.0
    low.loc[dates[12:], "BBB"] = 195.0
    low.loc[dates[13], "AAA"] = 94.0
    return close, open_prices, high, low


def run_managed_backtest(
    strategy: TradingStrategy,
    prices: tuple[pd.DataFrame, ...],
):
    close, open_prices, high, low = prices
    return backtest_strategies_vectorbt(
        strategies={strategy.name: strategy},
        prices=close,
        open=open_prices,
        high=high,
        low=low,
        rebalance_freq=2,
        rebalance_on="last",
        trading_start_date=close.index[10],
        freq="1D",
    )[strategy.name]


def test_donchian_stop_requires_full_history_and_never_moves_down() -> None:
    with pytest.raises(ValueError, match="trail_lookback_bars must be positive"):
        DonchianTrailingStopPolicy(trail_lookback_bars=0)

    policy = DonchianTrailingStopPolicy(trail_lookback_bars=10)

    assert (
        policy.refresh_stop(
            position_context(closed_low_history=(99.0,) * 9),
            previous_stop=None,
        )
        is None
    )
    assert policy.refresh_stop(
        position_context(closed_low_history=(91.0, *([97.0] * 9))),
        previous_stop=None,
    ) == pytest.approx(91.0)
    assert policy.refresh_stop(
        position_context(closed_low_history=(90.0, *([96.0] * 9))),
        previous_stop=95.0,
    ) == pytest.approx(95.0)
    assert policy.refresh_stop(
        position_context(closed_low_history=(97.0,) * 10),
        previous_stop=95.0,
    ) == pytest.approx(97.0)
    assert policy.refresh_stop(
        position_context(closed_low_history=(97.0,) * 9 + (np.nan,)),
        previous_stop=95.0,
    ) == pytest.approx(95.0)


def test_donchian_stop_triggers_on_touch_and_is_gap_aware() -> None:
    policy = DonchianTrailingStopPolicy(trail_lookback_bars=10)

    touch = policy.evaluate(
        position_context(active_stop_price=95.0, open_price=100.0, low_price=95.0)
    )
    gap = policy.evaluate(
        position_context(active_stop_price=95.0, open_price=93.0, low_price=92.0)
    )

    assert touch is not None
    assert touch.reason == "trailing_stop"
    assert touch.execution_price == pytest.approx(95.0)
    assert gap is not None
    assert gap.threshold_price == pytest.approx(95.0)
    assert gap.execution_price == pytest.approx(93.0)
    assert not hasattr(policy, "take_profit_pct")


def test_hold_lifecycle_keeps_positions_reweights_and_closes_removed_assets() -> None:
    close, open_prices, high, low = lifecycle_prices()
    strategy = build_managed_strategy()
    result = run_managed_backtest(strategy, (close, open_prices, high, low))
    dates = close.index

    assert result.weights.loc[dates[10], "AAA"] == pytest.approx(0.70)
    assert result.weights.loc[dates[12], "AAA"] == pytest.approx(0.35)
    assert result.weights.loc[dates[12], "BBB"] == pytest.approx(0.35)
    assert result.weights.loc[dates[13], "AAA"] == pytest.approx(0.0)
    assert pd.isna(result.weights.loc[dates[13], "BBB"])
    assert result.weights.loc[dates[14], "BBB"] == pytest.approx(0.70)
    assert result.weights.loc[dates[16]].sum() == pytest.approx(0.0)

    events = result.execution_events.set_index("reason")
    assert events.loc["trailing_stop", "ticker"] == "AAA"
    assert events.loc["trailing_stop", "execution_price"] == pytest.approx(95.0)
    assert events.loc["universe_removed", "ticker"] == "BBB"
    assert events.loc["universe_removed", "execution_price"] == pytest.approx(200.0)


def test_hold_lifecycle_does_not_reenter_on_the_stop_bar() -> None:
    close, open_prices, high, low = lifecycle_prices()
    low.loc[close.index[12], "AAA"] = 94.0
    strategy = build_managed_strategy(
        signals={10: {"AAA": 0.7}, 12: {"AAA": 0.35, "BBB": 0.35}}
    )
    result = run_managed_backtest(strategy, (close, open_prices, high, low))

    assert result.weights.loc[close.index[12], "AAA"] == pytest.approx(0.0)
    assert result.weights.loc[close.index[12], "BBB"] == pytest.approx(0.70)
    trailing_event = result.execution_events.query("reason == 'trailing_stop'").iloc[0]
    assert trailing_event["time"] == close.index[12]


def test_future_bars_do_not_change_managed_orders_or_exits() -> None:
    base_prices = lifecycle_prices(periods=19)
    base = run_managed_backtest(build_managed_strategy(), base_prices)

    extended_prices = lifecycle_prices(periods=22)
    extended_prices[3].loc[extended_prices[0].index[19] :, "BBB"] = 1.0
    extended = run_managed_backtest(build_managed_strategy(), extended_prices)
    cutoff = base_prices[0].index[-1]

    pd.testing.assert_frame_equal(
        base.weights.loc[:cutoff],
        extended.weights.loc[:cutoff],
    )
    pd.testing.assert_frame_equal(
        base.execution_events.reset_index(drop=True),
        extended.execution_events.loc[
            extended.execution_events["time"] <= cutoff
        ].reset_index(drop=True),
    )


def build_real_context() -> tuple[pd.DataFrame, ...]:
    dates = pd.bdate_range("2020-01-01", periods=570)
    close_values = np.asarray([100.0 + index * 0.1 for index in range(len(dates))])
    close = pd.DataFrame({"AAA": close_values}, index=dates)
    open_prices = close.copy()
    high = close + 0.01
    low = close - 1.0
    open_prices.loc[dates[554], "AAA"] = 150.0
    low.loc[dates[554], "AAA"] = 149.0
    context = pd.DataFrame(
        [
            {
                "time": timestamp,
                "ticker": "AAA",
                "open": open_prices.loc[timestamp, "AAA"],
                "high": high.loc[timestamp, "AAA"],
                "low": low.loc[timestamp, "AAA"],
                "close": close.loc[timestamp, "AAA"],
                "volume": 1_000_000.0,
                "is_complete": True,
            }
            for timestamp in dates
        ]
    )
    return close, open_prices, high, low, context


def test_full_builder_registry_and_backtest_smoke() -> None:
    close, open_prices, high, low, context = build_real_context()
    builder = ModelExtremumRangeLongOnlyTrailingStop10Builder(context)
    strategy = builder.build()

    assert isinstance(strategy.exit_policy, DonchianTrailingStopPolicy)
    assert strategy.exit_policy.trail_lookback_bars == 10
    assert strategy.position_lifecycle.mode == "hold_until_exit"
    assert strategy.position_lifecycle.allocation_pct == pytest.approx(0.70)
    assert strategy.position_lifecycle.close_on_universe_removal is True
    assert strategy.supports_live_execution is False
    assert strategy.metadata["entry_trigger"] == "rebalance_close"
    assert strategy.metadata["take_profit"] is None
    registered_builder = load_registered_trading_strategy(
        "ModelExtremumRangeLongOnlyTrailingStop10Builder"
    )
    assert (
        registered_builder.__name__ == "ModelExtremumRangeLongOnlyTrailingStop10Builder"
    )

    result = backtest_strategies_vectorbt(
        strategies={strategy.name: strategy},
        prices=close,
        open=open_prices,
        high=high,
        low=low,
        rebalance_freq=2,
        rebalance_on="last",
        trading_start_date=close.index[552],
        freq="1D",
    )[strategy.name]

    rebalance_weights = result.weights.dropna(how="all")
    assert not rebalance_weights.empty
    assert np.isfinite(rebalance_weights.to_numpy()).all()
    assert np.all(
        np.isclose(rebalance_weights.sum(axis=1), 0.0)
        | np.isclose(rebalance_weights.sum(axis=1), 0.70)
    )
    assert "trailing_stop" in set(result.execution_events["reason"])
