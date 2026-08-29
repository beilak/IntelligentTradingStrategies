import pandas as pd
import pytest

from its.strategies.core.signals import ExtremumRangeLongSignal


def signal_rows(
    ticker: str,
    closes: list[float],
    *,
    latest_high: float | None = None,
) -> list[dict]:
    dates = pd.date_range("2024-01-01", periods=len(closes), freq="D")
    rows = [
        {
            "time": date,
            "ticker": ticker,
            "high": close + 0.4,
            "close": close,
            "is_complete": True,
        }
        for date, close in zip(dates, closes, strict=True)
    ]
    if latest_high is not None:
        rows[-1]["high"] = latest_high
    return rows


def build_signal(context: pd.DataFrame) -> ExtremumRangeLongSignal:
    returns = pd.DataFrame(
        0.0,
        index=range(6),
        columns=["BELOW", "EQUAL", "ABOVE", "NO_GATE"],
    )
    return ExtremumRangeLongSignal(
        asset_universe_prices=context,
        channel_lookback_bars=3,
        ema_length=3,
        streak_length=2,
        gate_side="either",
    ).fit(returns)


def test_extremum_range_signal_selects_above_and_below_ema_streaks() -> None:
    context = pd.DataFrame(
        signal_rows("ABOVE", [100, 101, 102, 103, 104, 110])
        + signal_rows("BELOW", [110, 109, 108, 107, 106, 120])
        + signal_rows("EQUAL", [100, 101, 102, 103, 104, 104.4])
        + signal_rows("NO_GATE", [100, 99, 101, 100, 101, 110])
    )

    signal = build_signal(context)

    assert signal.to_keep_.tolist() == [True, False, True, False]
    assert signal.streak_side_.to_dict() == {
        "BELOW": "below",
        "EQUAL": "above",
        "ABOVE": "above",
        "NO_GATE": "none",
    }
    assert signal.channel_high_.loc["EQUAL"] == pytest.approx(104.4)
    assert signal.latest_close_.loc["EQUAL"] == pytest.approx(104.4)
    assert signal.gate_passed_.loc["NO_GATE"] == pytest.approx(False)
    assert signal.required_bars_ == 6


def test_extremum_range_signal_ignores_incomplete_future_candle() -> None:
    rows = signal_rows("ABOVE", [100, 101, 102, 103, 104, 110])
    rows.append(
        {
            "time": "2024-01-07",
            "ticker": "ABOVE",
            "high": 10_000.0,
            "close": 1.0,
            "is_complete": False,
        }
    )
    returns = pd.DataFrame({"ABOVE": [0.0] * 6})

    signal = ExtremumRangeLongSignal(
        asset_universe_prices=pd.DataFrame(rows),
        channel_lookback_bars=3,
        ema_length=3,
        streak_length=2,
    ).fit(returns)

    assert signal.to_keep_.tolist() == [True]
    assert signal.bars_used_.loc["ABOVE"] == 6
    assert signal.latest_close_.loc["ABOVE"] == 110


def test_extremum_range_signal_requires_551_bars_with_default_profile() -> None:
    dates = pd.date_range("2020-01-01", periods=550, freq="D")
    context = pd.DataFrame(
        {
            "time": dates,
            "ticker": "AAA",
            "high": [100 + index * 0.1 + 0.05 for index in range(len(dates))],
            "close": [100 + index * 0.1 for index in range(len(dates))],
            "is_complete": True,
        }
    )

    signal = ExtremumRangeLongSignal(asset_universe_prices=context).fit(
        pd.DataFrame({"AAA": [0.0] * len(dates)})
    )

    assert signal.required_bars_ == 551
    assert signal.bars_used_.loc["AAA"] == 550
    assert signal.to_keep_.tolist() == [False]


def test_extremum_range_signal_is_unchanged_when_future_is_truncated() -> None:
    decision_time = pd.Timestamp("2024-01-06")
    base = pd.DataFrame(signal_rows("AAA", [100, 101, 102, 103, 104, 110]))
    future = pd.concat(
        [
            base,
            pd.DataFrame(signal_rows("AAA", [1_000, 2_000])).assign(
                time=pd.date_range("2024-01-07", periods=2, freq="D")
            ),
        ],
        ignore_index=True,
    )
    returns = pd.DataFrame({"AAA": [0.0] * 6})
    baseline = ExtremumRangeLongSignal(
        asset_universe_prices=base,
        channel_lookback_bars=3,
        ema_length=3,
        streak_length=2,
    ).fit(returns)
    repeated = ExtremumRangeLongSignal(
        asset_universe_prices=future.loc[future["time"] <= decision_time],
        channel_lookback_bars=3,
        ema_length=3,
        streak_length=2,
    ).fit(returns)

    assert repeated.to_keep_.tolist() == baseline.to_keep_.tolist()
    assert repeated.channel_high_.equals(baseline.channel_high_)
    assert repeated.latest_close_.equals(baseline.latest_close_)


def test_extremum_range_signal_validates_parameters_and_columns() -> None:
    returns = pd.DataFrame({"AAA": [0.0]})
    with pytest.raises(ValueError, match="channel_lookback_bars"):
        ExtremumRangeLongSignal(channel_lookback_bars=0).fit(returns)
    with pytest.raises(ValueError, match="gate_side"):
        ExtremumRangeLongSignal(gate_side="both").fit(returns)
    with pytest.raises(ValueError, match="high"):
        ExtremumRangeLongSignal(
            asset_universe_prices=pd.DataFrame({"time": [], "ticker": [], "close": []})
        ).fit(returns)
