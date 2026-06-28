import pandas as pd

from its.strategies.core.signals import RangeLowProximitySignal


def test_range_low_proximity_signal_selects_wide_range_close_to_low() -> None:
    dates = pd.date_range("2024-01-01", periods=3, freq="D")
    returns = pd.DataFrame(
        0.0,
        index=dates,
        columns=["SELECTED", "TOO_NARROW", "TOO_FAR", "SHORT"],
    )
    values = {
        "SELECTED": [(100, 90, 96), (112, 91, 95), (105, 92, 92)],
        "TOO_NARROW": [(100, 95, 98), (102, 96, 98), (101, 95, 97)],
        "TOO_FAR": [(100, 80, 90), (110, 82, 95), (105, 81, 90)],
        "SHORT": [(120, 90, 92)],
    }
    candles = pd.DataFrame(
        [
            {
                "time": date,
                "ticker": ticker,
                "high": high,
                "low": low,
                "close": close,
                "is_complete": True,
            }
            for ticker, rows in values.items()
            for date, (high, low, close) in zip(dates, rows)
        ]
    )

    signal = RangeLowProximitySignal(
        lookback_bars=3,
        min_range_pct=0.10,
        max_close_to_low_pct=0.03,
        asset_universe_prices=candles,
    ).fit(returns)

    assert signal.to_keep_.tolist() == [True, False, False, False]
    assert list(signal.transform(returns).columns) == ["SELECTED"]
    assert signal.range_pct_.loc["SELECTED"] == (112 - 90) / 90
    assert signal.close_to_low_pct_.loc["SELECTED"] == (92 - 90) / 90
