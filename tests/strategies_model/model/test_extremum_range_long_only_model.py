import numpy as np
import pandas as pd
import pytest

from its.strategies.core.optimization import EqualWeightedWithCash
from its.strategies.core.selectors import QuarterlyTopTurnoverSelector
from its.strategies.core.signals import ExtremumRangeLongSignal
from its.strategies.models import ModelExtremumRangeLongOnlyBuilder
from its.strategies.testing.backtest.vectorbt_backtest import (
    backtest_strategies_vectorbt,
)


def build_fixture() -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = pd.bdate_range("2021-01-01", periods=556)
    aaa = np.asarray([100.0 + index * 0.1 for index in range(len(dates))])
    aaa[551:] = 154.0
    bbb = np.full(len(dates), 200.0)
    close = pd.DataFrame({"AAA": aaa, "BBB": bbb}, index=dates)
    context = pd.DataFrame(
        [
            {
                "time": date,
                "ticker": ticker,
                "open": value,
                "high": value + 0.05,
                "low": value - 0.05,
                "close": value,
                "volume": 1_000_000.0 if ticker == "AAA" else 500_000.0,
                "is_complete": True,
            }
            for date, aaa_value, bbb_value in zip(dates, aaa, bbb, strict=True)
            for ticker, value in (("AAA", aaa_value), ("BBB", bbb_value))
        ]
    )
    return close, context


def test_extremum_range_model_composition_and_frozen_parameters() -> None:
    _, context = build_fixture()
    strategy = ModelExtremumRangeLongOnlyBuilder(context).build()

    assert [name for name, _ in strategy.pipeline.steps] == [
        "quarterly_turnover_pre_selection",
        "extremum_range_long_signal",
        "allocation",
    ]
    selector = strategy.pipeline.named_steps["quarterly_turnover_pre_selection"]
    signal = strategy.pipeline.named_steps["extremum_range_long_signal"]
    allocator = strategy.pipeline.named_steps["allocation"]
    assert isinstance(selector, QuarterlyTopTurnoverSelector)
    assert isinstance(signal, ExtremumRangeLongSignal)
    assert isinstance(allocator, EqualWeightedWithCash)
    assert selector.top_n == 40
    assert selector.lookback_days == 252
    assert signal.channel_lookback_bars == 30
    assert signal.ema_length == 500
    assert signal.streak_length == 50
    assert signal.gate_side == "either"
    assert allocator.allocation_pct == pytest.approx(0.70)


def test_extremum_range_model_backtest_allocates_then_returns_to_cash() -> None:
    prices, context = build_fixture()
    strategy = ModelExtremumRangeLongOnlyBuilder(context).build()

    result = backtest_strategies_vectorbt(
        strategies={strategy.name: strategy},
        prices=prices,
        rebalance_freq=1,
        rebalance_on="last",
        trading_start_date=prices.index[551],
        freq="1D",
    )[strategy.name]

    weights = result.weights.dropna(how="all")
    assert not weights.empty
    assert weights.iloc[0]["AAA"] == pytest.approx(0.70)
    assert weights.iloc[0]["BBB"] == 0.0
    assert weights.iloc[0].sum() == pytest.approx(0.70)
    assert (weights.iloc[1:].sum(axis=1) == 0.0).any()
    assert np.isfinite(weights.to_numpy()).all()
    assert np.all(
        np.isclose(weights.sum(axis=1), 0.0) | np.isclose(weights.sum(axis=1), 0.70)
    )
