from datetime import UTC, datetime

import pandas as pd

from its.data_loader.t_invest_data_readers.utils import _datetime_to_timestamp
from services.data_backend.app.main import (
    PRICE_COLUMNS,
    build_price_summary,
    dataframe_to_records,
)


def test_tinvest_timestamp_is_converted_to_moscow_market_time() -> None:
    timestamp = _datetime_to_timestamp(datetime(2026, 5, 22, 21, 0, tzinfo=UTC))

    assert timestamp == pd.Timestamp("2026-05-23 00:00:00")


def test_tinvest_midnight_timestamp_is_not_treated_as_local_time() -> None:
    timestamp = _datetime_to_timestamp(datetime(2026, 5, 23, 0, 0, tzinfo=UTC))

    assert timestamp == pd.Timestamp("2026-05-23 03:00:00")


def test_price_records_serialize_time_with_market_timezone() -> None:
    prices = pd.DataFrame(
        [
            {
                "figi": "figi-1",
                "ticker": "TEST",
                "time": pd.Timestamp("2026-05-23 10:15:00"),
                "open": 100,
                "high": 102,
                "low": 99,
                "close": 101,
                "volume": 10,
                "is_complete": True,
            }
        ]
    )

    records = dataframe_to_records(prices, PRICE_COLUMNS)

    assert records[0]["time"] == "2026-05-23T10:15:00+03:00"


def test_price_summary_uses_market_timezone_for_from_to() -> None:
    prices = pd.DataFrame(
        [
            {
                "figi": "figi-1",
                "ticker": "TEST",
                "time": pd.Timestamp("2026-05-23"),
                "close": 100,
            },
            {
                "figi": "figi-1",
                "ticker": "TEST",
                "time": pd.Timestamp("2026-05-24"),
                "close": 110,
            },
        ]
    )

    summary = build_price_summary(prices)

    assert summary[0]["from"] == "2026-05-23T00:00:00+03:00"
    assert summary[0]["to"] == "2026-05-24T00:00:00+03:00"
