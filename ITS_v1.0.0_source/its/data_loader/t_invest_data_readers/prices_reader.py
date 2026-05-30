import asyncio
import functools
import math
from pathlib import Path

import aiometer
import pandas as pd
from grpc import StatusCode
from loguru import logger
from t_tech.invest import AsyncClient, CandleInterval
from t_tech.invest.exceptions import AioRequestError

from .utils import dataclasses_to_dict, get_max_requests_per_second

CACHE_DIR = Path(__file__).resolve().parents[2] / "data"
CACHE_FILE_PREFIX = "prices_moex"
CACHE_FILE_SUFFIXES = {
    CandleInterval.CANDLE_INTERVAL_5_SEC: "5s",
    CandleInterval.CANDLE_INTERVAL_10_SEC: "10s",
    CandleInterval.CANDLE_INTERVAL_30_SEC: "30s",
    CandleInterval.CANDLE_INTERVAL_1_MIN: "1min",
    CandleInterval.CANDLE_INTERVAL_2_MIN: "2min",
    CandleInterval.CANDLE_INTERVAL_3_MIN: "3min",
    CandleInterval.CANDLE_INTERVAL_5_MIN: "5min",
    CandleInterval.CANDLE_INTERVAL_10_MIN: "10min",
    CandleInterval.CANDLE_INTERVAL_15_MIN: "15min",
    CandleInterval.CANDLE_INTERVAL_30_MIN: "30min",
    CandleInterval.CANDLE_INTERVAL_HOUR: "h",
    CandleInterval.CANDLE_INTERVAL_2_HOUR: "2h",
    CandleInterval.CANDLE_INTERVAL_4_HOUR: "4h",
    CandleInterval.CANDLE_INTERVAL_DAY: "d",
    CandleInterval.CANDLE_INTERVAL_WEEK: "w",
    CandleInterval.CANDLE_INTERVAL_MONTH: "m",
}
CACHE_PATH = CACHE_DIR / f"{CACHE_FILE_PREFIX}_d.csv"
CACHE_INTERVAL_COLUMN = "cache_interval"
CACHE_START_COLUMN = "cache_requested_start"
CACHE_END_COLUMN = "cache_requested_end"
CACHE_COMPLETE_COLUMN = "cache_requested_is_complete"
CACHE_MARKER_COLUMN = "cache_marker"
CACHE_METADATA_COLUMNS = [
    CACHE_INTERVAL_COLUMN,
    CACHE_START_COLUMN,
    CACHE_END_COLUMN,
    CACHE_COMPLETE_COLUMN,
    CACHE_MARKER_COLUMN,
]

MAX_YEARS = 5


def _normalize_timestamp(value: pd.Timestamp) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_localize(None)
    return timestamp


def _coerce_bool(value: object) -> object:
    if pd.isna(value):
        return pd.NA
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1"}:
        return True
    if text in {"false", "0"}:
        return False
    return pd.NA


def _interval_to_cache_key(interval: CandleInterval) -> str:
    return interval.name


def _get_cache_path(interval: CandleInterval) -> Path:
    suffix = CACHE_FILE_SUFFIXES.get(interval, interval.name.lower())
    return CACHE_DIR / f"{CACHE_FILE_PREFIX}_{suffix}.csv"


def _interval_step(interval: CandleInterval):
    steps = {
        CandleInterval.CANDLE_INTERVAL_5_SEC: pd.Timedelta(seconds=5),
        CandleInterval.CANDLE_INTERVAL_10_SEC: pd.Timedelta(seconds=10),
        CandleInterval.CANDLE_INTERVAL_30_SEC: pd.Timedelta(seconds=30),
        CandleInterval.CANDLE_INTERVAL_1_MIN: pd.Timedelta(minutes=1),
        CandleInterval.CANDLE_INTERVAL_2_MIN: pd.Timedelta(minutes=2),
        CandleInterval.CANDLE_INTERVAL_3_MIN: pd.Timedelta(minutes=3),
        CandleInterval.CANDLE_INTERVAL_5_MIN: pd.Timedelta(minutes=5),
        CandleInterval.CANDLE_INTERVAL_10_MIN: pd.Timedelta(minutes=10),
        CandleInterval.CANDLE_INTERVAL_15_MIN: pd.Timedelta(minutes=15),
        CandleInterval.CANDLE_INTERVAL_30_MIN: pd.Timedelta(minutes=30),
        CandleInterval.CANDLE_INTERVAL_HOUR: pd.Timedelta(hours=1),
        CandleInterval.CANDLE_INTERVAL_2_HOUR: pd.Timedelta(hours=2),
        CandleInterval.CANDLE_INTERVAL_4_HOUR: pd.Timedelta(hours=4),
        CandleInterval.CANDLE_INTERVAL_DAY: pd.Timedelta(days=1),
        CandleInterval.CANDLE_INTERVAL_WEEK: pd.Timedelta(weeks=1),
        CandleInterval.CANDLE_INTERVAL_MONTH: pd.DateOffset(months=1),
    }
    return steps.get(interval, pd.Timedelta(nanoseconds=1))


def _shift_timestamp(value: pd.Timestamp, interval: CandleInterval) -> pd.Timestamp:
    return pd.Timestamp(value + _interval_step(interval))


def _ensure_cache_columns(prices: pd.DataFrame) -> pd.DataFrame:
    prices = prices.copy()

    if CACHE_INTERVAL_COLUMN not in prices.columns:
        prices[CACHE_INTERVAL_COLUMN] = pd.NA
    if CACHE_START_COLUMN not in prices.columns:
        prices[CACHE_START_COLUMN] = pd.NaT
    if CACHE_END_COLUMN not in prices.columns:
        prices[CACHE_END_COLUMN] = pd.NaT
    if CACHE_COMPLETE_COLUMN not in prices.columns:
        prices[CACHE_COMPLETE_COLUMN] = pd.NA
    if CACHE_MARKER_COLUMN not in prices.columns:
        prices[CACHE_MARKER_COLUMN] = False

    return prices


def _read_cache_file(cache_path: Path) -> pd.DataFrame:
    if not cache_path.exists():
        return pd.DataFrame()

    try:
        cache = pd.read_csv(cache_path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()

    cache = _ensure_cache_columns(cache)

    for column in ["time", CACHE_START_COLUMN, CACHE_END_COLUMN]:
        if column in cache.columns:
            cache[column] = pd.to_datetime(cache[column], errors="coerce")

    for column in [CACHE_COMPLETE_COLUMN, CACHE_MARKER_COLUMN, "is_complete"]:
        if column in cache.columns:
            cache[column] = cache[column].map(_coerce_bool)

    if CACHE_MARKER_COLUMN in cache.columns:
        cache[CACHE_MARKER_COLUMN] = (
            cache[CACHE_MARKER_COLUMN].fillna(False).astype(bool)
        )

    return cache


def _finalize_prices(prices: pd.DataFrame, *, is_complete: bool) -> pd.DataFrame:
    if prices.empty:
        return prices.drop(columns=CACHE_METADATA_COLUMNS, errors="ignore")

    prices = prices.copy()
    prices = prices.drop(columns=CACHE_METADATA_COLUMNS, errors="ignore")

    if "time" in prices.columns:
        prices["time"] = pd.to_datetime(prices["time"], errors="coerce")
        prices = prices.loc[prices["time"].notna()].copy()

    if is_complete and "is_complete" in prices.columns:
        prices["is_complete"] = prices["is_complete"].map(_coerce_bool)
        prices = prices.loc[prices["is_complete"].fillna(False)].copy()

    if "time" in prices.columns:
        prices = prices.sort_values(["figi", "time"]).drop_duplicates(
            subset=["figi", "time"], keep="last"
        )

    return prices.reset_index(drop=True)


def _merge_covered_ranges(
    covered_ranges: list[tuple[pd.Timestamp, pd.Timestamp]],
    interval: CandleInterval,
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    if not covered_ranges:
        return []

    merged_ranges: list[list[pd.Timestamp]] = []

    for range_start, range_end in sorted(covered_ranges):
        if not merged_ranges:
            merged_ranges.append([range_start, range_end])
            continue

        previous_start, previous_end = merged_ranges[-1]
        if range_start <= _shift_timestamp(previous_end, interval):
            merged_ranges[-1][1] = max(previous_end, range_end)
            continue

        merged_ranges.append([range_start, range_end])

    return [(range_start, range_end) for range_start, range_end in merged_ranges]


def _get_missing_ranges(
    covered_ranges: list[tuple[pd.Timestamp, pd.Timestamp]],
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    interval: CandleInterval,
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    if start_date > end_date:
        return []

    merged_ranges = _merge_covered_ranges(covered_ranges, interval)
    missing_ranges: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    cursor = start_date

    for covered_start, covered_end in merged_ranges:
        if covered_end < start_date or covered_start > end_date:
            continue

        covered_start = max(covered_start, start_date)
        covered_end = min(covered_end, end_date)

        if covered_start > cursor:
            missing_ranges.append((cursor, covered_start))

        cursor = max(cursor, _shift_timestamp(covered_end, interval))

        if cursor > end_date:
            break

    if cursor <= end_date:
        missing_ranges.append((cursor, end_date))

    return missing_ranges


def _build_cache_rows(
    prices: pd.DataFrame,
    figi: str,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    interval: CandleInterval,
    is_complete: bool,
) -> pd.DataFrame:
    cache_key = _interval_to_cache_key(interval)
    cache_start = _normalize_timestamp(start_date)
    cache_end = _normalize_timestamp(end_date)

    marker_row = pd.DataFrame(
        [
            {
                "figi": figi,
                "time": pd.NaT,
                CACHE_INTERVAL_COLUMN: cache_key,
                CACHE_START_COLUMN: cache_start,
                CACHE_END_COLUMN: cache_end,
                CACHE_COMPLETE_COLUMN: is_complete,
                CACHE_MARKER_COLUMN: True,
            }
        ]
    )

    if prices is None or prices.empty:
        return marker_row

    cache_prices = prices.copy()
    cache_prices[CACHE_INTERVAL_COLUMN] = cache_key
    cache_prices[CACHE_START_COLUMN] = cache_start
    cache_prices[CACHE_END_COLUMN] = cache_end
    cache_prices[CACHE_COMPLETE_COLUMN] = is_complete
    cache_prices[CACHE_MARKER_COLUMN] = False

    return pd.concat([cache_prices, marker_row], ignore_index=True, sort=False)


def _write_prices_cache(cache_rows: pd.DataFrame, cache_path: Path) -> None:
    if cache_rows.empty:
        return

    existing_cache = _read_cache_file(cache_path)
    combined_cache = pd.concat(
        [existing_cache, cache_rows], ignore_index=True, sort=False
    )
    combined_cache = _ensure_cache_columns(combined_cache)

    for column in ["time", CACHE_START_COLUMN, CACHE_END_COLUMN]:
        if column in combined_cache.columns:
            combined_cache[column] = pd.to_datetime(
                combined_cache[column], errors="coerce"
            )

    for column in [CACHE_COMPLETE_COLUMN, CACHE_MARKER_COLUMN, "is_complete"]:
        if column in combined_cache.columns:
            combined_cache[column] = combined_cache[column].map(_coerce_bool)

    combined_cache[CACHE_MARKER_COLUMN] = (
        combined_cache[CACHE_MARKER_COLUMN].fillna(False).astype(bool)
    )

    marker_rows = combined_cache.loc[combined_cache[CACHE_MARKER_COLUMN]].copy()
    price_rows = combined_cache.loc[~combined_cache[CACHE_MARKER_COLUMN]].copy()

    if not price_rows.empty:
        price_rows = price_rows.sort_values(
            [CACHE_INTERVAL_COLUMN, "figi", "time"]
        ).drop_duplicates(
            subset=[CACHE_INTERVAL_COLUMN, "figi", "time"],
            keep="last",
        )

    if not marker_rows.empty:
        marker_rows = marker_rows.sort_values(
            [CACHE_INTERVAL_COLUMN, "figi", CACHE_START_COLUMN, CACHE_END_COLUMN]
        ).drop_duplicates(
            subset=[
                CACHE_INTERVAL_COLUMN,
                "figi",
                CACHE_START_COLUMN,
                CACHE_END_COLUMN,
                CACHE_COMPLETE_COLUMN,
            ],
            keep="last",
        )

    cache_to_save = pd.concat([price_rows, marker_rows], ignore_index=True, sort=False)
    cache_to_save = cache_to_save.sort_values(
        [CACHE_INTERVAL_COLUMN, "figi", CACHE_START_COLUMN, "time"],
        na_position="last",
    )

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_to_save.to_csv(cache_path, index=False)


def read_prices_from_cache(
    figis: list[str],
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    interval: CandleInterval = CandleInterval.CANDLE_INTERVAL_DAY,
    is_complete: bool = True,
    cache_path: Path | None = None,
) -> tuple[pd.DataFrame, dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]]]:
    start_date = _normalize_timestamp(start_date)
    end_date = _normalize_timestamp(end_date)
    unique_figis = list(dict.fromkeys(figis))

    if not unique_figis or start_date > end_date:
        return pd.DataFrame(), {}

    if cache_path is None:
        cache_path = _get_cache_path(interval)

    cache = _read_cache_file(cache_path)
    if cache.empty:
        return pd.DataFrame(), {figi: [(start_date, end_date)] for figi in unique_figis}

    interval_mask = (
        cache[CACHE_INTERVAL_COLUMN].eq(_interval_to_cache_key(interval)).fillna(False)
    )
    complete_mask = cache[CACHE_COMPLETE_COLUMN].eq(is_complete).fillna(False)
    figi_mask = cache["figi"].isin(unique_figis)

    filtered_cache = cache.loc[figi_mask & interval_mask & complete_mask].copy()

    if filtered_cache.empty:
        return pd.DataFrame(), {figi: [(start_date, end_date)] for figi in unique_figis}

    marker_mask = filtered_cache[CACHE_MARKER_COLUMN]

    cached_prices = filtered_cache.loc[~marker_mask].copy()
    if "time" in cached_prices.columns:
        cached_prices = cached_prices.loc[
            cached_prices["time"].between(start_date, end_date, inclusive="both")
        ].copy()

    missing_ranges: dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]] = {}

    for figi in unique_figis:
        figi_markers = filtered_cache.loc[
            marker_mask
            & filtered_cache["figi"].eq(figi)
            & filtered_cache[CACHE_START_COLUMN].notna()
            & filtered_cache[CACHE_END_COLUMN].notna(),
            [CACHE_START_COLUMN, CACHE_END_COLUMN],
        ]

        covered_ranges = list(figi_markers.itertuples(index=False, name=None))
        figi_missing_ranges = _get_missing_ranges(
            covered_ranges=covered_ranges,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
        )

        if figi_missing_ranges:
            missing_ranges[figi] = figi_missing_ranges

    return _finalize_prices(cached_prices, is_complete=is_complete), missing_ranges


def _split_date_range(
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    start_date = _normalize_timestamp(start_date)
    end_date = _normalize_timestamp(end_date)

    if start_date > end_date:
        return []

    current_from = start_date
    ranges: list[tuple[pd.Timestamp, pd.Timestamp]] = []

    while current_from <= end_date:
        current_to = min(
            current_from + pd.Timedelta(days=365 * MAX_YEARS),
            end_date,
        )
        ranges.append((current_from, current_to))

        if current_to == end_date:
            break

        current_from = current_to

    return ranges


async def _get_price(
    figi: str,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    client: AsyncClient,
    interval: CandleInterval = CandleInterval.CANDLE_INTERVAL_DAY,
    is_complete: bool = True,
):
    response = []

    for i in range(0, 3):
        try:
            response = [
                candle
                async for candle in client.get_all_candles(
                    figi=figi,
                    from_=start_date,
                    to=end_date,
                    interval=interval,
                )
            ]
            break
        except AioRequestError as error:
            logger.info(f"{error = }")
            if error.code == StatusCode.RESOURCE_EXHAUSTED:
                logger.info(
                    f"Лимит исчерпан. Ждем {error.metadata.ratelimit_reset} сек."
                )
                await asyncio.sleep(error.metadata.ratelimit_reset)
                if i >= 2:
                    raise
                continue
            if error.code == StatusCode.NOT_FOUND or i >= 2:
                raise

    raw_candles = dataclasses_to_dict(response)

    prices = pd.DataFrame(raw_candles).assign(figi=figi)

    if prices.empty:
        logger.warning(f"No candles for {figi} ({start_date}-{end_date})")
        return prices

    if "is_complete" in prices.columns and is_complete:
        prices = prices.query("is_complete").copy()

    if interval == CandleInterval.CANDLE_INTERVAL_DAY:
        prices.time = prices.time.map(pd.Timestamp.normalize)

    return prices


async def _download_prices(
    missing_ranges: dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]],
    token: str,
    max_per_second: float | None,
    interval: CandleInterval,
    is_complete: bool,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    job_specs: list[tuple[str, pd.Timestamp, pd.Timestamp]] = []

    for figi, figi_ranges in missing_ranges.items():
        for range_start, range_end in figi_ranges:
            for current_from, current_to in _split_date_range(range_start, range_end):
                job_specs.append((figi, current_from, current_to))

    if not job_specs:
        return pd.DataFrame(), pd.DataFrame()

    if max_per_second is None:
        max_per_second = await get_max_requests_per_second(token)

    max_at_once = max(1, math.ceil(max_per_second))

    async with AsyncClient(token) as client:
        jobs = [
            functools.partial(
                _get_price,
                figi,
                current_from,
                current_to,
                client=client,
                interval=interval,
                is_complete=is_complete,
            )
            for figi, current_from, current_to in job_specs
        ]
        raw_prices = await aiometer.run_all(
            jobs,
            max_at_once=max_at_once,
            max_per_second=max_per_second,
        )

    downloaded_prices = []
    cache_rows = []

    for (figi, chunk_start, chunk_end), prices in zip(
        job_specs, raw_prices, strict=True
    ):
        cache_rows.append(
            _build_cache_rows(
                prices=prices,
                figi=figi,
                start_date=chunk_start,
                end_date=chunk_end,
                interval=interval,
                is_complete=is_complete,
            )
        )
        if prices is not None and not prices.empty:
            downloaded_prices.append(prices)

    prices_df = pd.DataFrame()
    if downloaded_prices:
        prices_df = _finalize_prices(
            pd.concat(downloaded_prices, axis=0, ignore_index=True, sort=False),
            is_complete=is_complete,
        )

    cache_df = pd.DataFrame()
    if cache_rows:
        cache_df = pd.concat(cache_rows, axis=0, ignore_index=True, sort=False)

    return prices_df, cache_df


async def get_prices(
    figis: list[str],
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    token: str,
    max_per_second: float | None = None,
    interval: CandleInterval = CandleInterval.CANDLE_INTERVAL_DAY,
    is_complete: bool = True,
) -> pd.DataFrame:
    start_date = _normalize_timestamp(start_date)
    end_date = _normalize_timestamp(end_date)
    unique_figis = list(dict.fromkeys(figis))

    if not unique_figis or start_date > end_date:
        return pd.DataFrame()

    cache_path = _get_cache_path(interval)
    cached_prices, missing_ranges = read_prices_from_cache(
        figis=unique_figis,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
        is_complete=is_complete,
        cache_path=cache_path,
    )

    downloaded_prices = pd.DataFrame()
    if missing_ranges:
        downloaded_prices, cache_rows = await _download_prices(
            missing_ranges=missing_ranges,
            token=token,
            max_per_second=max_per_second,
            interval=interval,
            is_complete=is_complete,
        )
        _write_prices_cache(cache_rows, cache_path=cache_path)

    if cached_prices.empty and downloaded_prices.empty:
        return pd.DataFrame()

    return _finalize_prices(
        pd.concat(
            [cached_prices, downloaded_prices], axis=0, ignore_index=True, sort=False
        ),
        is_complete=is_complete,
    )
