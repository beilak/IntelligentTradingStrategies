import pandas as pd
import pytest

from its.strategies.core.selectors import QuarterlyTopTurnoverSelector


def candle_rows(
    ticker: str,
    dates: list[str],
    *,
    volume: float,
    is_complete: bool = True,
) -> list[dict]:
    return [
        {
            "time": pd.Timestamp(date) + pd.Timedelta(hours=hour),
            "ticker": ticker,
            "open": 100.0,
            "high": 100.0,
            "low": 100.0,
            "close": 100.0,
            "volume": volume,
            "is_complete": is_complete,
        }
        for date in dates
        for hour in (10, 14)
    ]


def test_quarterly_top_turnover_selects_top_n_and_preserves_column_order() -> None:
    q1_dates = ["2024-03-26", "2024-03-27", "2024-03-28"]
    rows = (
        candle_rows("HIGH", q1_dates, volume=30.0)
        + candle_rows("MID", q1_dates, volume=20.0)
        + candle_rows("LOW", q1_dates, volume=10.0)
        + candle_rows("LOW", ["2024-03-29"], volume=1_000_000.0, is_complete=False)
        + candle_rows("LOW", ["2024-04-01"], volume=1_000_000.0)
    )
    returns = pd.DataFrame(0.0, index=range(4), columns=["LOW", "HIGH", "MID"])

    selector = QuarterlyTopTurnoverSelector(
        asset_universe_prices=pd.DataFrame(rows),
        top_n=2,
        lookback_days=3,
        min_history_days=3,
    ).fit(returns)

    assert selector.to_keep_.tolist() == [False, True, True]
    assert list(selector.transform(returns).columns) == ["HIGH", "MID"]
    assert selector.selected_assets_.tolist() == ["HIGH", "MID"]
    assert selector.ranking_date_ == pd.Timestamp("2024-03-28")
    assert selector.turnover_summary_.set_index("ticker").loc[
        "HIGH", "mean_daily_turnover"
    ] == pytest.approx(6_000.0)


def test_quarterly_top_turnover_keeps_membership_then_updates_next_quarter() -> None:
    q1_dates = ["2024-03-26", "2024-03-27", "2024-03-28"]
    q2_dates = ["2024-04-01", "2024-04-02", "2024-05-10"]
    rows = (
        candle_rows("HIGH", q1_dates, volume=30.0)
        + candle_rows("LOW", q1_dates, volume=10.0)
        + candle_rows("HIGH", q2_dates, volume=5.0)
        + candle_rows("LOW", q2_dates, volume=100.0)
    )
    returns = pd.DataFrame(0.0, index=range(4), columns=["HIGH", "LOW"])
    intra_quarter = pd.DataFrame(rows)

    q2_selector = QuarterlyTopTurnoverSelector(
        asset_universe_prices=intra_quarter,
        top_n=1,
        lookback_days=3,
        min_history_days=3,
    ).fit(returns)

    next_quarter_context = pd.concat(
        [
            intra_quarter,
            pd.DataFrame(candle_rows("HIGH", ["2024-07-01"], volume=5.0)),
        ],
        ignore_index=True,
    )
    q3_selector = QuarterlyTopTurnoverSelector(
        asset_universe_prices=next_quarter_context,
        top_n=1,
        lookback_days=3,
        min_history_days=3,
    ).fit(returns)

    assert q2_selector.selected_assets_.tolist() == ["HIGH"]
    assert q3_selector.selected_assets_.tolist() == ["LOW"]
    assert q3_selector.ranking_date_ == pd.Timestamp("2024-05-10")


def test_quarterly_top_turnover_is_unchanged_when_future_is_truncated() -> None:
    q1_dates = ["2024-03-26", "2024-03-27", "2024-03-28"]
    base = pd.DataFrame(
        candle_rows("HIGH", q1_dates, volume=30.0)
        + candle_rows("LOW", q1_dates, volume=10.0)
        + candle_rows("HIGH", ["2024-04-01"], volume=5.0)
        + candle_rows("LOW", ["2024-04-01"], volume=100.0)
    )
    future = pd.concat(
        [
            base,
            pd.DataFrame(candle_rows("LOW", ["2024-07-01"], volume=1_000.0)),
        ],
        ignore_index=True,
    )
    decision_time = pd.Timestamp("2024-04-01 23:59:59")
    returns = pd.DataFrame(0.0, index=range(4), columns=["HIGH", "LOW"])

    baseline = QuarterlyTopTurnoverSelector(
        asset_universe_prices=base,
        top_n=1,
        lookback_days=3,
        min_history_days=3,
    ).fit(returns)
    repeated = QuarterlyTopTurnoverSelector(
        asset_universe_prices=future.loc[future["time"] <= decision_time],
        top_n=1,
        lookback_days=3,
        min_history_days=3,
    ).fit(returns)

    assert repeated.to_keep_.tolist() == baseline.to_keep_.tolist()
    assert repeated.turnover_summary_.equals(baseline.turnover_summary_)


def test_quarterly_top_turnover_allows_empty_selection_for_short_history() -> None:
    rows = candle_rows("AAA", ["2024-03-27", "2024-03-28"], volume=10.0)
    rows += candle_rows("AAA", ["2024-04-01"], volume=10.0)
    returns = pd.DataFrame({"AAA": [0.0, 0.0], "BBB": [0.0, 0.0]})

    selector = QuarterlyTopTurnoverSelector(
        asset_universe_prices=pd.DataFrame(rows),
        top_n=1,
        lookback_days=3,
        min_history_days=3,
    ).fit(returns)

    assert selector.to_keep_.tolist() == [False, False]
    assert list(selector.transform(returns).columns) == []
    assert selector.turnover_summary_.empty


def test_quarterly_top_turnover_validates_configuration_and_columns() -> None:
    returns = pd.DataFrame({"AAA": [0.0]})
    with pytest.raises(ValueError, match="top_n"):
        QuarterlyTopTurnoverSelector(top_n=0).fit(returns)
    with pytest.raises(ValueError, match="min_history_days"):
        QuarterlyTopTurnoverSelector(
            lookback_days=2,
            min_history_days=3,
        ).fit(returns)
    with pytest.raises(ValueError, match="volume"):
        QuarterlyTopTurnoverSelector(
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
