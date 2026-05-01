import warnings

import numpy as np
import pandas as pd

from its.strategies.core.signals import TwoCandlePositiveTrendSignal


def test_two_candle_signal_treats_zero_previous_prices_as_invalid_returns() -> None:
    prices = pd.DataFrame(
        {
            "CLEAN": [100.0, 101.0, 102.0],
            "ZERO_BASE": [0.0, 1.0, 2.0],
        }
    )

    signal = TwoCandlePositiveTrendSignal(n_candles=2, min_pct_increase=0)

    with warnings.catch_warnings(record=True) as caught_warnings:
        warnings.simplefilter("always")
        signal.fit(prices)

    assert caught_warnings == []
    assert np.array_equal(signal.to_keep_, np.array([True, False]))
