import numpy as np
import pandas as pd
import pytest

from its.strategies.core.signals import CloseBelowRecentMarkerSignal


def test_close_below_recent_high_signal_selects_pullback_assets() -> None:
    returns = pd.DataFrame(
        {
            "PULLBACK": [0.0, 0.01, -0.02],
            "NEAR_HIGH": [0.0, 0.01, -0.01],
            "SHORT_HISTORY": [0.0, 0.01, -0.01],
        }
    )
    candles = pd.DataFrame(
        [
            {
                "time": "2024-01-01",
                "ticker": "PULLBACK",
                "high": 100.0,
                "close": 98.0,
                "is_complete": True,
            },
            {
                "time": "2024-01-02",
                "ticker": "PULLBACK",
                "high": 120.0,
                "close": 115.0,
                "is_complete": True,
            },
            {
                "time": "2024-01-03",
                "ticker": "PULLBACK",
                "high": 118.0,
                "close": 107.0,
                "is_complete": True,
            },
            {
                "time": "2024-01-01",
                "ticker": "NEAR_HIGH",
                "high": 100.0,
                "close": 99.0,
                "is_complete": True,
            },
            {
                "time": "2024-01-02",
                "ticker": "NEAR_HIGH",
                "high": 101.0,
                "close": 100.0,
                "is_complete": True,
            },
            {
                "time": "2024-01-03",
                "ticker": "NEAR_HIGH",
                "high": 100.0,
                "close": 95.0,
                "is_complete": True,
            },
            {
                "time": "2024-01-03",
                "ticker": "SHORT_HISTORY",
                "high": 120.0,
                "close": 100.0,
                "is_complete": True,
            },
        ]
    )

    signal = CloseBelowRecentMarkerSignal(
        marker="high",
        lookback_bars=3,
        threshold_pct=0.1,
        asset_universe_prices=candles,
    ).fit(returns)
    transformed = signal.transform(returns)

    assert signal.to_keep_.tolist() == [True, False, False]
    assert list(transformed.columns) == ["PULLBACK"]
    assert signal.marker_values_.loc["PULLBACK"] == 120.0
    assert signal.threshold_values_.loc["PULLBACK"] == 108.0
    assert signal.latest_close_.loc["PULLBACK"] == 107.0


def test_close_below_recent_close_signal_can_use_wide_close_prices() -> None:
    close = pd.DataFrame(
        {
            "PULLBACK": [100.0, 120.0, 115.0, 108.0],
            "NEAR_HIGH": [100.0, 101.0, 100.0, 95.0],
        }
    )

    signal = CloseBelowRecentMarkerSignal(
        marker="close",
        lookback_bars=3,
        threshold_pct=0.1,
    ).fit(close)
    transformed = signal.transform(close)

    assert signal.to_keep_.tolist() == [True, False]
    assert list(transformed.columns) == ["PULLBACK"]


def test_close_below_recent_high_signal_requires_price_context() -> None:
    close = pd.DataFrame({"A": [100.0, 90.0, 80.0]})

    with pytest.raises(ValueError, match="asset_universe_prices"):
        CloseBelowRecentMarkerSignal(
            marker="high",
            lookback_bars=3,
            threshold_pct=0.1,
        ).fit(close)


def test_close_below_recent_marker_signal_validates_parameters() -> None:
    close = np.asarray([[100.0], [90.0]])

    with pytest.raises(ValueError, match="marker"):
        CloseBelowRecentMarkerSignal(marker="low").fit(close)

    with pytest.raises(ValueError, match="lookback_bars"):
        CloseBelowRecentMarkerSignal(marker="close", lookback_bars=0).fit(close)

    with pytest.raises(ValueError, match="threshold_pct"):
        CloseBelowRecentMarkerSignal(marker="close", threshold_pct=1.0).fit(close)
