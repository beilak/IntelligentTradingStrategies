import numpy as np
import pandas as pd
import pytest

from its.strategies.core.selectors import EquityLiquiditySelector


def candle_rows(
    ticker: str,
    dates: list[str],
    *,
    volume: float,
    price: float = 100.0,
    is_complete: bool = True,
) -> list[dict]:
    return [
        {
            "time": pd.Timestamp(date) + pd.Timedelta(hours=hour),
            "ticker": ticker,
            "open": price,
            "high": price,
            "low": price,
            "close": price,
            "volume": volume,
            "is_complete": is_complete,
        }
        for date in dates
        for hour in (10, 14)
    ]


def test_equity_liquidity_selects_by_mean_daily_turnover_and_preserves_order() -> None:
    dates = ["2024-03-26", "2024-03-27", "2024-03-28"]
    rows = (
        candle_rows("HIGH", dates, volume=10_000.0)
        + candle_rows("MID", dates, volume=6_000.0)
        + candle_rows("LOW", dates, volume=1_000.0)
    )
    returns = pd.DataFrame(0.0, index=range(3), columns=["LOW", "HIGH", "MID"])

    selector = EquityLiquiditySelector(
        asset_universe_prices=pd.DataFrame(rows),
        lookback_days=3,
        min_avg_daily_turnover_rub=500_000.0,
        min_history_days=3,
    ).fit(returns)

    assert selector.to_keep_.tolist() == [False, True, True]
    assert list(selector.transform(returns).columns) == ["HIGH", "MID"]
    assert selector.selected_assets_.tolist() == ["HIGH", "MID"]
    summary = selector.turnover_summary_.set_index("ticker")
    assert summary.loc["HIGH", "mean_daily_turnover"] == pytest.approx(2_000_000.0)


def test_equity_liquidity_threshold_boundary_is_inclusive() -> None:
    dates = ["2024-03-26", "2024-03-27", "2024-03-28"]
    rows = candle_rows("EDGE", dates, volume=5_000.0)
    returns = pd.DataFrame(0.0, index=range(3), columns=["EDGE"])
    threshold = 1_000_000.0

    below = EquityLiquiditySelector(
        asset_universe_prices=pd.DataFrame(rows),
        lookback_days=3,
        min_avg_daily_turnover_rub=threshold + 0.01,
        min_history_days=3,
    ).fit(returns)
    at = EquityLiquiditySelector(
        asset_universe_prices=pd.DataFrame(rows),
        lookback_days=3,
        min_avg_daily_turnover_rub=threshold,
        min_history_days=3,
    ).fit(returns)

    assert below.to_keep_.tolist() == [False]
    assert at.to_keep_.tolist() == [True]


def test_equity_liquidity_excludes_insufficient_history() -> None:
    rows = candle_rows("SHORT", ["2024-03-27", "2024-03-28"], volume=10_000.0)
    rows += candle_rows(
        "FULL", ["2024-03-26", "2024-03-27", "2024-03-28"], volume=10_000.0
    )
    returns = pd.DataFrame(0.0, index=range(3), columns=["SHORT", "FULL"])

    selector = EquityLiquiditySelector(
        asset_universe_prices=pd.DataFrame(rows),
        lookback_days=3,
        min_avg_daily_turnover_rub=0.0,
        min_history_days=3,
    ).fit(returns)

    assert selector.to_keep_.tolist() == [False, True]


def test_equity_liquidity_ignores_incomplete_and_incorrect_candles() -> None:
    dates = ["2024-03-26", "2024-03-27", "2024-03-28"]
    rows = candle_rows("GOOD", dates, volume=10_000.0)
    rows += candle_rows("BAD", dates, volume=10_000.0, is_complete=False)
    rows.append(
        {
            "time": pd.Timestamp("2024-03-26 10:00"),
            "ticker": "BAD",
            "open": 100.0,
            "high": -5.0,
            "low": 100.0,
            "close": 100.0,
            "volume": 10_000.0,
            "is_complete": True,
        }
    )
    returns = pd.DataFrame(0.0, index=range(3), columns=["GOOD", "BAD"])

    selector = EquityLiquiditySelector(
        asset_universe_prices=pd.DataFrame(rows),
        lookback_days=3,
        min_avg_daily_turnover_rub=0.0,
        min_history_days=3,
    ).fit(returns)

    assert selector.to_keep_.tolist() == [True, False]


def test_equity_liquidity_allows_empty_selection() -> None:
    dates = ["2024-03-26", "2024-03-27", "2024-03-28"]
    rows = candle_rows("AAA", dates, volume=1_000.0)
    returns = pd.DataFrame(0.0, index=range(3), columns=["AAA"])

    selector = EquityLiquiditySelector(
        asset_universe_prices=pd.DataFrame(rows),
        lookback_days=3,
        min_avg_daily_turnover_rub=10_000_000.0,
        min_history_days=3,
    ).fit(returns)

    assert selector.to_keep_.tolist() == [False]
    assert not selector.to_keep_.any()


def test_equity_liquidity_validates_configuration_and_columns() -> None:
    returns = pd.DataFrame({"AAA": [0.0]})
    with pytest.raises(ValueError, match="lookback_days"):
        EquityLiquiditySelector(lookback_days=0).fit(returns)
    with pytest.raises(ValueError, match="min_avg_daily_turnover_rub"):
        EquityLiquiditySelector(min_avg_daily_turnover_rub=-1.0).fit(returns)
    with pytest.raises(ValueError, match="min_history_days"):
        EquityLiquiditySelector(lookback_days=2, min_history_days=3).fit(returns)
    with pytest.raises(ValueError, match="asset_universe_prices is required"):
        EquityLiquiditySelector().fit(returns)
    with pytest.raises(ValueError, match="volume"):
        EquityLiquiditySelector(
            asset_universe_prices=pd.DataFrame(
                {
                    "time": [],
                    "ticker": [],
                    "open": [],
                    "high": [],
                    "low": [],
                    "close": [],
                }
            )
        ).fit(returns)


def test_equity_liquidity_is_unchanged_when_future_is_truncated() -> None:
    dates = ["2024-03-26", "2024-03-27", "2024-03-28"]
    base = pd.DataFrame(
        candle_rows("HIGH", dates, volume=10_000.0)
        + candle_rows("LOW", dates, volume=1_000.0)
    )
    future = pd.concat(
        [
            base,
            pd.DataFrame(candle_rows("LOW", ["2024-04-01"], volume=100_000.0)),
        ],
        ignore_index=True,
    )
    decision_time = pd.Timestamp("2024-03-28 23:59:59")
    returns = pd.DataFrame(0.0, index=range(3), columns=["HIGH", "LOW"])

    baseline = EquityLiquiditySelector(
        asset_universe_prices=base,
        lookback_days=3,
        min_avg_daily_turnover_rub=2_000_000.0,
        min_history_days=3,
    ).fit(returns)
    repeated = EquityLiquiditySelector(
        asset_universe_prices=future.loc[future["time"] <= decision_time],
        lookback_days=3,
        min_avg_daily_turnover_rub=2_000_000.0,
        min_history_days=3,
    ).fit(returns)

    assert repeated.to_keep_.tolist() == baseline.to_keep_.tolist()
    assert repeated.turnover_summary_.equals(baseline.turnover_summary_)


def test_equity_liquidity_handles_numpy_input_with_generated_names() -> None:
    dates = ["2024-03-26", "2024-03-27", "2024-03-28"]
    rows = candle_rows("asset_1", dates, volume=10_000.0)
    returns = np.zeros((3, 2))

    selector = EquityLiquiditySelector(
        asset_universe_prices=pd.DataFrame(rows),
        lookback_days=3,
        min_avg_daily_turnover_rub=2_000_000.0,
        min_history_days=3,
    ).fit(returns)

    assert selector.to_keep_.tolist() == [False, True]
