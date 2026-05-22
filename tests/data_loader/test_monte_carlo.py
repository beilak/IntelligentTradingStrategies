from datetime import date

import pandas as pd
import pytest

from its.data_loader.monte_carlo import build_close_price_monte_carlo


def test_close_price_monte_carlo_uses_training_cutoff_and_close_only() -> None:
    prices = pd.DataFrame(
        {
            "time": pd.date_range("2024-01-01", periods=6, freq="D"),
            "close": [100.0, 102.0, 104.0, 105.0, 103.0, 106.0],
            "open": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
            "figi": ["FIGI"] * 6,
            "ticker": ["TST"] * 6,
        }
    )

    result = build_close_price_monte_carlo(
        prices,
        train_until=date(2024, 1, 3),
        simulation_end=date(2024, 1, 6),
        path_count=3,
        seed=7,
        volatility_scale=0,
        interval="CANDLE_INTERVAL_DAY",
    )

    assert result.meta["training_points"] == 3
    assert result.meta["simulation_steps"] == 3
    assert result.training["close"].tolist() == [100.0, 102.0, 104.0]
    assert result.paths["path_id"].nunique() == 3

    first_points = result.paths.loc[result.paths["step"] == 0]
    assert first_points["close"].tolist() == [104.0, 104.0, 104.0]


def test_close_price_monte_carlo_requires_two_training_prices() -> None:
    prices = pd.DataFrame(
        {
            "time": pd.date_range("2024-01-01", periods=3, freq="D"),
            "close": [100.0, 101.0, 102.0],
        }
    )

    with pytest.raises(ValueError, match="At least two training close prices"):
        build_close_price_monte_carlo(
            prices,
            train_until=date(2024, 1, 1),
            simulation_end=date(2024, 1, 3),
        )
