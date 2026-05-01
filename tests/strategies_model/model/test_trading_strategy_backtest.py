import pandas as pd
import pytest

from its.strategies.core.types.strategy_types import Strategy as CoreStrategy
from its.strategies.testing.backtest.vectorbt_backtest import backtest_strategies_vectorbt
from its.strategies_model.core.trading_strategy import (
    FixedStopTakeProfitPolicy,
    PositionContext,
    TradingStrategy,
)


class FakePrediction:
    weights_dict = {"AAA": 1.0}


class FakePipeline:
    def fit(self, x_train: pd.DataFrame) -> "FakePipeline":
        return self

    def predict(self, x_test: pd.DataFrame) -> FakePrediction:
        return FakePrediction()


def test_fixed_stop_take_profit_prefers_stop_when_both_trigger() -> None:
    policy = FixedStopTakeProfitPolicy(stop_loss_pct=0.01, take_profit_pct=0.03)

    decision = policy.evaluate(
        PositionContext(
            ticker="AAA",
            entry_time=pd.Timestamp("2024-01-01"),
            current_time=pd.Timestamp("2024-01-02"),
            entry_price=100,
            current_price=101,
            high_price=104,
            low_price=98,
            weight=1,
        )
    )

    assert decision is not None
    assert decision.reason == "stop_loss"
    assert decision.execution_price == 99
    assert decision.return_pct == pytest.approx(-0.01)


def test_trading_strategy_backtest_adds_take_profit_exit_event() -> None:
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    close = pd.DataFrame({"AAA": [100, 100, 103, 102, 102]}, index=dates)
    high = pd.DataFrame({"AAA": [100, 100, 104, 102, 102]}, index=dates)
    low = pd.DataFrame({"AAA": [100, 100, 102, 101, 101]}, index=dates)
    core = CoreStrategy(
        name="fake_core",
        description="Fake always-long core.",
        pipeline=FakePipeline(),
    )
    strategy = TradingStrategy(
        name="managed",
        description="Managed fake strategy.",
        core=core,
        exit_policy=FixedStopTakeProfitPolicy(stop_loss_pct=0.01, take_profit_pct=0.03),
    )

    result = backtest_strategies_vectorbt(
        strategies={strategy.name: strategy},
        prices=close,
        high=high,
        low=low,
        rebalance_freq="2D",
        rebalance_on="last",
        trading_start_date=dates[0],
        freq="1D",
    )[strategy.name]

    assert len(result.execution_events) == 1
    event = result.execution_events.iloc[0]
    assert event["ticker"] == "AAA"
    assert event["reason"] == "take_profit"
    assert event["execution_price"] == 103
    assert result.weights.loc[pd.Timestamp("2024-01-03"), "AAA"] == 0
