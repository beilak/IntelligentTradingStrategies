import pandas as pd
from t_tech.invest import CandleInterval

from its.data_loader.t_invest_data_readers.prices_reader import (
    _build_cache_rows,
    _get_cache_path,
    _write_prices_cache,
    read_prices_from_cache,
)


def test_cache_path_uses_interval_suffix() -> None:
    assert (
        _get_cache_path(CandleInterval.CANDLE_INTERVAL_DAY).name == "prices_moex_d.csv"
    )
    assert (
        _get_cache_path(CandleInterval.CANDLE_INTERVAL_HOUR).name == "prices_moex_h.csv"
    )
    assert (
        _get_cache_path(CandleInterval.CANDLE_INTERVAL_15_MIN).name
        == "prices_moex_15min.csv"
    )


def test_cache_files_are_isolated_by_interval(tmp_path) -> None:
    figi = "figi-1"
    day_cache = tmp_path / "prices_moex_d.csv"
    hour_cache = tmp_path / "prices_moex_h.csv"
    start = pd.Timestamp("2026-01-01")
    end = pd.Timestamp("2026-01-02")

    day_prices = pd.DataFrame(
        [
            {
                "figi": figi,
                "time": pd.Timestamp("2026-01-01"),
                "open": 100,
                "high": 102,
                "low": 99,
                "close": 101,
                "is_complete": True,
            }
        ]
    )
    hour_prices = pd.DataFrame(
        [
            {
                "figi": figi,
                "time": pd.Timestamp("2026-01-01 10:00:00"),
                "open": 101,
                "high": 103,
                "low": 100,
                "close": 102,
                "is_complete": True,
            }
        ]
    )

    _write_prices_cache(
        _build_cache_rows(
            day_prices,
            figi,
            start,
            end,
            CandleInterval.CANDLE_INTERVAL_DAY,
            True,
        ),
        cache_path=day_cache,
    )
    _write_prices_cache(
        _build_cache_rows(
            hour_prices,
            figi,
            start,
            end,
            CandleInterval.CANDLE_INTERVAL_HOUR,
            True,
        ),
        cache_path=hour_cache,
    )

    cached_day_prices, day_missing_ranges = read_prices_from_cache(
        [figi],
        start,
        end,
        interval=CandleInterval.CANDLE_INTERVAL_DAY,
        is_complete=True,
        cache_path=day_cache,
    )
    cached_hour_prices, hour_missing_ranges = read_prices_from_cache(
        [figi],
        start,
        end,
        interval=CandleInterval.CANDLE_INTERVAL_HOUR,
        is_complete=True,
        cache_path=hour_cache,
    )

    assert day_missing_ranges == {}
    assert hour_missing_ranges == {}
    assert cached_day_prices.iloc[0]["close"] == 101
    assert cached_hour_prices.iloc[0]["close"] == 102
    assert cached_day_prices.iloc[0]["time"] != cached_hour_prices.iloc[0]["time"]
