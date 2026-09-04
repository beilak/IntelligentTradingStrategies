from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pandas as pd
import pytest
from grpc import StatusCode
from t_tech.invest import CandleInterval
from t_tech.invest.exceptions import AioRequestError

from its.data_loader.t_invest_data_readers.prices_reader import (
    CACHE_COMPLETE_COLUMN,
    CACHE_END_COLUMN,
    CACHE_INTERVAL_COLUMN,
    CACHE_MARKER_COLUMN,
    CACHE_SCHEMA_COLUMN,
    CACHE_SCHEMA_VERSION,
    CACHE_START_COLUMN,
    _build_cache_rows,
    _get_cache_path,
    _get_price,
    _write_prices_cache,
    read_prices_from_cache,
)


@dataclass
class CandleStub:
    time: datetime
    close: float
    is_complete: bool


class CandleClientStub:
    def __init__(self, candles: list[CandleStub]) -> None:
        self.candles = candles
        self.request: dict[str, object] = {}

    def get_all_candles(self, **kwargs):
        self.request = kwargs

        async def iterate_candles():
            for candle in self.candles:
                yield candle

        return iterate_candles()


class TransientFailureCandleClientStub(CandleClientStub):
    def __init__(self, candles: list[CandleStub], failures: int) -> None:
        super().__init__(candles)
        self.failures = failures
        self.attempts = 0

    def get_all_candles(self, **kwargs):
        self.request = kwargs

        async def iterate_candles():
            self.attempts += 1
            if self.attempts <= self.failures:
                raise AioRequestError(
                    StatusCode.UNKNOWN,
                    "Stream removed (Data frame with END_STREAM flag received)",
                    SimpleNamespace(ratelimit_reset=None),
                )
            for candle in self.candles:
                yield candle

        return iterate_candles()


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


def test_cache_read_ignores_unversioned_coverage_markers(tmp_path) -> None:
    figi = "figi-1"
    cache_path = tmp_path / "prices_moex_d.csv"
    start = pd.Timestamp("2026-05-23")
    end = pd.Timestamp("2026-05-24")

    pd.DataFrame(
        [
            {
                "figi": figi,
                "time": pd.NaT,
                CACHE_INTERVAL_COLUMN: CandleInterval.CANDLE_INTERVAL_DAY.name,
                CACHE_START_COLUMN: start,
                CACHE_END_COLUMN: end,
                CACHE_COMPLETE_COLUMN: True,
                CACHE_MARKER_COLUMN: True,
            }
        ]
    ).to_csv(cache_path, index=False)

    cached_prices, missing_ranges = read_prices_from_cache(
        [figi],
        start,
        end,
        interval=CandleInterval.CANDLE_INTERVAL_DAY,
        is_complete=True,
        cache_path=cache_path,
    )

    assert cached_prices.empty
    assert missing_ranges == {figi: [(start, end)]}


def test_cache_read_includes_exact_left_boundary(tmp_path) -> None:
    figi = "figi-1"
    cache_path = tmp_path / "prices_moex_d.csv"
    start = pd.Timestamp("2026-05-23")
    end = pd.Timestamp("2026-05-24")
    prices = pd.DataFrame(
        [
            {
                "figi": figi,
                "time": start,
                "open": 100,
                "high": 103,
                "low": 99,
                "close": 102,
                "is_complete": True,
            }
        ]
    )

    _write_prices_cache(
        _build_cache_rows(
            prices,
            figi,
            start,
            end,
            CandleInterval.CANDLE_INTERVAL_DAY,
            True,
        ),
        cache_path=cache_path,
    )

    cached_prices, missing_ranges = read_prices_from_cache(
        [figi],
        start,
        end,
        interval=CandleInterval.CANDLE_INTERVAL_DAY,
        is_complete=True,
        cache_path=cache_path,
    )

    assert missing_ranges == {}
    assert cached_prices["time"].tolist() == [start]


def test_daily_eod_marker_advances_to_next_day_midnight(tmp_path) -> None:
    figi = "figi-1"
    cache_path = tmp_path / "prices_moex_d.csv"
    requested_start = pd.Timestamp("2026-08-10")
    marker_end = pd.Timestamp("2026-08-10 23:59:59.999999")
    requested_end = pd.Timestamp("2026-08-13 23:59:59.999999")

    pd.DataFrame(
        [
            {
                "figi": figi,
                "time": pd.NaT,
                CACHE_INTERVAL_COLUMN: CandleInterval.CANDLE_INTERVAL_DAY.name,
                CACHE_START_COLUMN: requested_start,
                CACHE_END_COLUMN: marker_end,
                CACHE_COMPLETE_COLUMN: True,
                CACHE_MARKER_COLUMN: True,
                CACHE_SCHEMA_COLUMN: CACHE_SCHEMA_VERSION,
            }
        ]
    ).to_csv(cache_path, index=False)

    cached_prices, missing_ranges = read_prices_from_cache(
        [figi],
        requested_start,
        requested_end,
        interval=CandleInterval.CANDLE_INTERVAL_DAY,
        is_complete=True,
        cache_path=cache_path,
    )

    assert cached_prices.empty
    assert missing_ranges == {
        figi: [(pd.Timestamp("2026-08-11"), pd.Timestamp("2026-08-13"))]
    }


def test_incomplete_daily_candle_is_refreshed_after_it_closes(tmp_path) -> None:
    figi = "figi-1"
    cache_path = tmp_path / "prices_moex_d.csv"
    requested_start = pd.Timestamp("2026-08-10")
    requested_end = pd.Timestamp("2026-08-13 23:59:59.999999")
    initial_prices = pd.DataFrame(
        [
            {
                "figi": figi,
                "time": pd.Timestamp(f"2026-08-{day:02d}"),
                "close": 100 + day,
                "is_complete": day < 13,
            }
            for day in range(10, 14)
        ]
    )

    _write_prices_cache(
        _build_cache_rows(
            initial_prices,
            figi,
            requested_start,
            requested_end,
            CandleInterval.CANDLE_INTERVAL_DAY,
            True,
            now=pd.Timestamp("2026-08-13 12:00:00", tz="Europe/Moscow"),
        ),
        cache_path=cache_path,
    )

    cached_prices, missing_ranges = read_prices_from_cache(
        [figi],
        requested_start,
        requested_end,
        interval=CandleInterval.CANDLE_INTERVAL_DAY,
        is_complete=True,
        cache_path=cache_path,
    )

    assert cached_prices["time"].tolist() == list(
        pd.date_range("2026-08-10", "2026-08-12", freq="D")
    )
    assert missing_ranges == {
        figi: [(pd.Timestamp("2026-08-13"), pd.Timestamp("2026-08-13"))]
    }

    completed_price = initial_prices.tail(1).assign(is_complete=True, close=999)
    _write_prices_cache(
        _build_cache_rows(
            completed_price,
            figi,
            pd.Timestamp("2026-08-13"),
            requested_end,
            CandleInterval.CANDLE_INTERVAL_DAY,
            True,
            now=pd.Timestamp("2026-08-14 12:00:00", tz="Europe/Moscow"),
        ),
        cache_path=cache_path,
    )

    refreshed_prices, refreshed_missing_ranges = read_prices_from_cache(
        [figi],
        requested_start,
        requested_end,
        interval=CandleInterval.CANDLE_INTERVAL_DAY,
        is_complete=True,
        cache_path=cache_path,
    )

    assert refreshed_missing_ranges == {}
    assert refreshed_prices["time"].tolist() == list(
        pd.date_range("2026-08-10", "2026-08-13", freq="D")
    )
    assert refreshed_prices.iloc[-1]["close"] == 999


def test_empty_download_does_not_create_permanent_coverage_marker() -> None:
    cache_rows = _build_cache_rows(
        pd.DataFrame(),
        "figi-1",
        pd.Timestamp("2026-08-13"),
        pd.Timestamp("2026-08-13 23:59:59.999999"),
        CandleInterval.CANDLE_INTERVAL_DAY,
        True,
        now=pd.Timestamp("2026-08-13 12:00:00", tz="Europe/Moscow"),
    )

    assert cache_rows.empty


@pytest.mark.asyncio
async def test_price_download_keeps_incomplete_tail_for_cache_refresh() -> None:
    client = CandleClientStub(
        [
            CandleStub(
                time=datetime(2026, 8, 12, tzinfo=UTC),
                close=100,
                is_complete=True,
            ),
            CandleStub(
                time=datetime(2026, 8, 13, tzinfo=UTC),
                close=101,
                is_complete=False,
            ),
        ]
    )

    prices = await _get_price(
        "figi-1",
        pd.Timestamp("2026-08-10"),
        pd.Timestamp("2026-08-13 23:59:59.999999"),
        client=client,
        interval=CandleInterval.CANDLE_INTERVAL_DAY,
        is_complete=True,
    )

    assert prices["time"].tolist() == [
        pd.Timestamp("2026-08-12"),
        pd.Timestamp("2026-08-13"),
    ]
    assert prices["is_complete"].tolist() == [True, False]
    request_end = pd.Timestamp(client.request["to"])
    assert request_end.tz_convert("Europe/Moscow") == pd.Timestamp(
        "2026-08-14",
        tz="Europe/Moscow",
    )


@pytest.mark.asyncio
async def test_price_download_retries_transient_stream_removal(monkeypatch) -> None:
    client = TransientFailureCandleClientStub(
        [
            CandleStub(
                time=datetime(2026, 8, 12, tzinfo=UTC),
                close=100,
                is_complete=True,
            )
        ],
        failures=2,
    )
    sleep = AsyncMock()
    monkeypatch.setattr(
        "its.data_loader.t_invest_data_readers.prices_reader.asyncio.sleep",
        sleep,
    )

    prices = await _get_price(
        "figi-1",
        pd.Timestamp("2026-08-10"),
        pd.Timestamp("2026-08-13"),
        client=client,
        interval=CandleInterval.CANDLE_INTERVAL_DAY,
    )

    assert client.attempts == 3
    assert prices["close"].tolist() == [100]
    assert [call.args[0] for call in sleep.await_args_list] == [1.0, 2.0]


def test_complete_and_all_candle_cache_rows_do_not_overwrite_each_other(
    tmp_path,
) -> None:
    figi = "figi-1"
    cache_path = tmp_path / "prices_moex_d.csv"
    candle_time = pd.Timestamp("2026-01-10")

    for requested_complete, close in [(True, 101), (False, 202)]:
        prices = pd.DataFrame(
            [
                {
                    "figi": figi,
                    "time": candle_time,
                    "close": close,
                    "is_complete": True,
                }
            ]
        )
        _write_prices_cache(
            _build_cache_rows(
                prices,
                figi,
                candle_time,
                candle_time,
                CandleInterval.CANDLE_INTERVAL_DAY,
                requested_complete,
                now=pd.Timestamp("2026-02-01", tz="Europe/Moscow"),
            ),
            cache_path=cache_path,
        )

    complete_prices, complete_missing = read_prices_from_cache(
        [figi],
        candle_time,
        candle_time,
        interval=CandleInterval.CANDLE_INTERVAL_DAY,
        is_complete=True,
        cache_path=cache_path,
    )
    all_prices, all_missing = read_prices_from_cache(
        [figi],
        candle_time,
        candle_time,
        interval=CandleInterval.CANDLE_INTERVAL_DAY,
        is_complete=False,
        cache_path=cache_path,
    )

    assert complete_missing == {}
    assert all_missing == {}
    assert complete_prices.iloc[0]["close"] == 101
    assert all_prices.iloc[0]["close"] == 202
