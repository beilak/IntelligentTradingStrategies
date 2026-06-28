from types import SimpleNamespace

import pandas as pd
from sklearn.pipeline import Pipeline

from its.strategies.core.optimization import HierarchicalRiskParity
from its.strategies.core.selectors import SectorSelector
from its.strategies.core.signals.pass_signals import KeepAllSignal
from its.strategies.core.types.strategy_types import Strategy
from its.strategies.testing.backtest.vectorbt_backtest import (
    _limit_pipeline_price_context, _make_schedule,
    backtest_strategies_vectorbt)


def test_month_end_schedule_is_anchored_to_first_trading_date() -> None:
    index = pd.bdate_range("2018-05-01", "2019-05-01")

    schedule = _make_schedule(index, "3ME", "last")

    assert list(schedule[:5]) == [
        pd.Timestamp("2018-05-01"),
        pd.Timestamp("2018-07-31"),
        pd.Timestamp("2018-10-31"),
        pd.Timestamp("2019-01-31"),
        pd.Timestamp("2019-04-30"),
    ]


def test_integer_schedule_starts_on_first_trading_date() -> None:
    index = pd.date_range("2024-01-01", periods=5, freq="D")

    schedule = _make_schedule(index, 2, "last")

    assert list(schedule) == [
        pd.Timestamp("2024-01-01"),
        pd.Timestamp("2024-01-03"),
        pd.Timestamp("2024-01-05"),
    ]


def test_weekly_first_schedule_starts_in_next_calendar_week() -> None:
    index = pd.bdate_range("2024-06-27", "2024-07-15")

    schedule = _make_schedule(index, "1W", "first")

    assert list(schedule[:3]) == [
        pd.Timestamp("2024-07-01"),
        pd.Timestamp("2024-07-08"),
        pd.Timestamp("2024-07-15"),
    ]


def test_three_month_end_first_schedule_uses_calendar_period_boundaries() -> None:
    index = pd.bdate_range("2024-06-27", "2025-07-05")

    schedule = _make_schedule(index, "3ME", "first")

    assert list(schedule[:5]) == [
        pd.Timestamp("2024-07-01"),
        pd.Timestamp("2024-10-01"),
        pd.Timestamp("2025-01-01"),
        pd.Timestamp("2025-04-01"),
        pd.Timestamp("2025-07-01"),
    ]


def test_pipeline_price_context_advances_between_rebalances() -> None:
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    signal = SimpleNamespace(
        asset_universe_prices=pd.DataFrame(
            {
                "time": dates,
                "ticker": ["AAA"] * len(dates),
                "close": range(len(dates)),
            }
        )
    )
    strategy = SimpleNamespace(pipeline=SimpleNamespace(steps=[("signal", signal)]))

    _limit_pipeline_price_context(strategy, dates[1])
    assert signal.asset_universe_prices["time"].max() == dates[1]

    _limit_pipeline_price_context(strategy, dates[3])
    assert signal.asset_universe_prices["time"].max() == dates[3]


def test_backtest_ignores_unavailable_assets_on_early_rebalance() -> None:
    index = pd.bdate_range("2018-01-01", "2018-12-31")
    prices = pd.DataFrame(
        {
            "OLD1": [100 + i for i in range(len(index))],
            "OLD2": [120 + i * 0.5 + (i % 3) for i in range(len(index))],
            "FUTURE": [float("nan")] * 180 + [80 + i for i in range(len(index) - 180)],
        },
        index=index,
    )
    assets_info = pd.DataFrame(
        [
            {"ticker": "OLD1", "sector": "it"},
            {"ticker": "OLD2", "sector": "telecom"},
            {"ticker": "FUTURE", "sector": "it"},
        ]
    )
    strategy = Strategy(
        name="hrp",
        description="HRP with sector filter.",
        pipeline=Pipeline(
            steps=[
                ("pre_selection", SectorSelector(assets_info, ["it", "telecom"])),
                ("signal", KeepAllSignal()),
                ("allocation", HierarchicalRiskParity(raise_on_failure=False)),
            ]
        ),
    )

    result = backtest_strategies_vectorbt(
        strategies={strategy.name: strategy},
        prices=prices,
        rebalance_freq="3ME",
        rebalance_on="last",
        trading_start_date=pd.Timestamp("2018-05-01"),
        freq="1D",
    )[strategy.name]

    first_weights = result.weights.dropna(how="all").iloc[0]

    assert result.rebalance_dates[0] == pd.Timestamp("2018-05-01")
    assert first_weights[["OLD1", "OLD2"]].sum() == 1
    assert first_weights["FUTURE"] == 0
