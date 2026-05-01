import asyncio
from pathlib import Path
import aiometer
from async_lru import alru_cache

import functools
import pandas as pd
from grpc import StatusCode
from loguru import logger
from t_tech.invest import AsyncClient, GetDividendsResponse
from t_tech.invest.exceptions import AioRequestError

from .utils import dataclasses_to_dict, get_max_requests_per_second

CACHE_DIR = Path(__file__).resolve().parents[2] / "data"
CACHE_FILE_PREFIX = "dividends"
CACHE_FILE_SUFFIX = "csv"
CACHE_PATH = CACHE_DIR / f"{CACHE_FILE_PREFIX}.{CACHE_FILE_SUFFIX}"
CACHE_START_COLUMN = "cache_requested_start"
CACHE_END_COLUMN = "cache_requested_end"
CACHE_MARKER_COLUMN = "cache_marker"
CACHE_METADATA_COLUMNS = [
    CACHE_START_COLUMN,
    CACHE_END_COLUMN,
    CACHE_MARKER_COLUMN,
]


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


def _ensure_cache_columns(dividends: pd.DataFrame) -> pd.DataFrame:
    dividends = dividends.copy()

    if CACHE_START_COLUMN not in dividends.columns:
        dividends[CACHE_START_COLUMN] = pd.NaT
    if CACHE_END_COLUMN not in dividends.columns:
        dividends[CACHE_END_COLUMN] = pd.NaT
    if CACHE_MARKER_COLUMN not in dividends.columns:
        dividends[CACHE_MARKER_COLUMN] = False

    return dividends


def _read_cache_file(cache_path: Path) -> pd.DataFrame:
    if not cache_path.exists():
        return pd.DataFrame()

    try:
        cache = pd.read_csv(cache_path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()

    cache = _ensure_cache_columns(cache)

    for column in [
        "payment_date",
        "declared_date",
        "last_buy_date",
        "record_date",
        CACHE_START_COLUMN,
        CACHE_END_COLUMN,
    ]:
        if column in cache.columns:
            cache[column] = pd.to_datetime(cache[column], errors="coerce")

    if CACHE_MARKER_COLUMN in cache.columns:
        cache[CACHE_MARKER_COLUMN] = (
            cache[CACHE_MARKER_COLUMN].fillna(False).astype(bool)
        )

    return cache


def _write_cache(cache_rows: pd.DataFrame, cache_path: Path) -> None:
    if cache_rows.empty:
        return

    existing_cache = _read_cache_file(cache_path)
    combined_cache = pd.concat(
        [existing_cache, cache_rows], ignore_index=True, sort=False
    )
    combined_cache = _ensure_cache_columns(combined_cache)

    for column in [
        "payment_date",
        "declared_date",
        "last_buy_date",
        "record_date",
        CACHE_START_COLUMN,
        CACHE_END_COLUMN,
    ]:
        if column in combined_cache.columns:
            combined_cache[column] = pd.to_datetime(
                combined_cache[column], errors="coerce"
            )

    if CACHE_MARKER_COLUMN in combined_cache.columns:
        combined_cache[CACHE_MARKER_COLUMN] = (
            combined_cache[CACHE_MARKER_COLUMN].fillna(False).astype(bool)
        )

    marker_rows = combined_cache.loc[combined_cache[CACHE_MARKER_COLUMN]].copy()
    dividend_rows = combined_cache.loc[~combined_cache[CACHE_MARKER_COLUMN]].copy()

    if not dividend_rows.empty:
        dividend_rows = dividend_rows.sort_values(
            ["figi", "payment_date"]
        ).drop_duplicates(
            subset=["figi", "payment_date"],
            keep="last",
        )

    if not marker_rows.empty:
        marker_rows = marker_rows.sort_values(
            ["figi", CACHE_START_COLUMN, CACHE_END_COLUMN]
        ).drop_duplicates(
            subset=["figi", CACHE_START_COLUMN, CACHE_END_COLUMN],
            keep="last",
        )

    cache_to_save = pd.concat(
        [dividend_rows, marker_rows], ignore_index=True, sort=False
    )
    cache_to_save = cache_to_save.sort_values(
        ["figi", "payment_date"],
        na_position="last",
    )

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_to_save.to_csv(cache_path, index=False)


def _get_missing_ranges(
    cached_dividends: pd.DataFrame,
    figis: list[str],
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]]:
    unique_figis = list(dict.fromkeys(figis))
    ranges = {figi: [(start_date, end_date)] for figi in unique_figis}

    if cached_dividends.empty or start_date > end_date:
        return ranges

    for figi in unique_figis:
        figi_cache = cached_dividends.loc[cached_dividends["figi"] == figi].copy()
        if figi_cache.empty:
            continue

        figi_cache = figi_cache.sort_values("payment_date")
        figi_ranges: list[tuple[pd.Timestamp, pd.Timestamp]] = []
        current_start = start_date

        for _, row in figi_cache.iterrows():
            payment_date = row.get("payment_date")
            if payment_date is None or pd.isna(payment_date):
                continue
            payment_date = pd.Timestamp(payment_date)
            if payment_date < start_date or payment_date > end_date:
                continue
            if payment_date < current_start:
                continue

            figi_ranges.append((current_start, payment_date - pd.Timedelta(days=1)))
            current_start = payment_date + pd.Timedelta(days=1)

        if current_start <= end_date:
            figi_ranges.append((current_start, end_date))

        ranges[figi] = figi_ranges

    return ranges


def read_dividends_from_cache(
    figis: list[str],
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    cache_path: Path | None = None,
) -> tuple[pd.DataFrame, dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]]]:
    start_date = _normalize_timestamp(start_date)
    end_date = _normalize_timestamp(end_date)
    unique_figis = list(dict.fromkeys(figis))

    if not unique_figis or start_date > end_date:
        return pd.DataFrame(), {figi: [(start_date, end_date)] for figi in unique_figis}

    if cache_path is None:
        cache_path = CACHE_PATH

    cache = _read_cache_file(cache_path)
    if cache.empty:
        return pd.DataFrame(), {figi: [(start_date, end_date)] for figi in unique_figis}

    figi_mask = cache["figi"].isin(unique_figis)
    filtered_cache = cache.loc[figi_mask].copy()

    if filtered_cache.empty:
        return pd.DataFrame(), {figi: [(start_date, end_date)] for figi in unique_figis}

    marker_mask = filtered_cache[CACHE_MARKER_COLUMN]
    cached_dividends = filtered_cache.loc[~marker_mask].copy()

    if "payment_date" in cached_dividends.columns:
        cached_dividends = cached_dividends.loc[
            cached_dividends["payment_date"].between(
                start_date, end_date, inclusive="both"
            )
        ].copy()

    missing_ranges = _get_missing_ranges(
        filtered_cache,
        unique_figis,
        start_date,
        end_date,
    )

    return cached_dividends, missing_ranges


def _build_cache_rows(
    dividends: pd.DataFrame,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> pd.DataFrame:
    if dividends.empty:
        return pd.DataFrame()

    cache_rows = dividends.copy()
    cache_rows[CACHE_START_COLUMN] = start_date
    cache_rows[CACHE_END_COLUMN] = end_date
    cache_rows[CACHE_MARKER_COLUMN] = True

    return cache_rows


@alru_cache(ttl=100)
async def _get_dividend(
    figi: str,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    client: AsyncClient,
):
    try:
        divs: GetDividendsResponse = await client.instruments.get_dividends(
            figi=figi,
            from_=start_date,
            to=end_date,
        )
        response = [dividend for dividend in divs.dividends]
    except AioRequestError as error:
        logger.info(f"{error = }")
        if error.code == StatusCode.RESOURCE_EXHAUSTED:
            logger.info(f"Лимит исчерпан. Ждем {error.metadata.ratelimit_reset} сек.")
            await asyncio.sleep(error.metadata.ratelimit_reset)
        raise

    raw_dividends = dataclasses_to_dict(response)

    dividends = pd.DataFrame(raw_dividends).assign(figi=figi)

    if dividends.empty:
        logger.warning(f"No dividends for {figi} ({start_date}-{end_date})")
        return dividends

    if "dividend_type" in dividends.columns:
        dividends = dividends.loc[dividends["dividend_type"] != "Cancelled"].copy()

    if "payment_date" in dividends.columns:
        dividends = dividends.loc[
            (dividends["payment_date"].notna())
            & (dividends["payment_date"] > start_date)
            & (dividends["payment_date"] < end_date + pd.Timedelta(days=1))
        ].copy()

    return dividends


async def _download_dividends(
    missing_ranges: dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]],
    token: str,
    max_per_second: float | None,
    cache_path: Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    job_specs: list[tuple[str, pd.Timestamp, pd.Timestamp]] = []

    for figi, figi_ranges in missing_ranges.items():
        for range_start, range_end in figi_ranges:
            job_specs.append((figi, range_start, range_end))

    if not job_specs:
        return pd.DataFrame(), pd.DataFrame()

    if max_per_second is None:
        max_per_second = await get_max_requests_per_second(token)

    max_at_once = max(1, int(max_per_second))

    async with AsyncClient(token) as client:
        jobs = [
            functools.partial(
                _get_dividend,
                figi,
                current_from,
                current_to,
                client=client,
            )
            for figi, current_from, current_to in job_specs
        ]
        raw_dividends = await aiometer.run_all(
            jobs,
            max_at_once=max_at_once,
            max_per_second=max_per_second,
        )

    downloaded_dividends = []
    cache_rows = []

    for (figi, current_from, current_to), dividends in zip(job_specs, raw_dividends):
        if not dividends.empty:
            downloaded_dividends.append(dividends)
            cache_rows.append(_build_cache_rows(dividends, current_from, current_to))

    if downloaded_dividends:
        all_dividends = pd.concat(downloaded_dividends, ignore_index=True)
    else:
        all_dividends = pd.DataFrame()
    if cache_rows:
        all_cache_rows = pd.concat(cache_rows, ignore_index=True)
    else:
        all_cache_rows = pd.DataFrame()

    if not all_cache_rows.empty and cache_path is not None:
        _write_cache(all_cache_rows, cache_path)

    return all_dividends, all_cache_rows


async def get_dividends(
    figis: list[str],
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    token: str,
    max_per_second: float | None = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    start_date = _normalize_timestamp(start_date)
    end_date = _normalize_timestamp(end_date)
    unique_figis = list(dict.fromkeys(figis))

    if not unique_figis:
        return pd.DataFrame()

    cache_path = CACHE_PATH if use_cache else None

    if use_cache:
        cached_dividends, missing_ranges = read_dividends_from_cache(
            unique_figis,
            start_date,
            end_date,
            cache_path,
        )
    else:
        cached_dividends = pd.DataFrame()
        missing_ranges = {figi: [(start_date, end_date)] for figi in unique_figis}

    if all(not ranges for ranges in missing_ranges.values()):
        return cached_dividends

    downloaded_dividends, _ = await _download_dividends(
        missing_ranges,
        token,
        max_per_second,
        cache_path,
    )

    all_dividends = pd.concat(
        [cached_dividends, downloaded_dividends], ignore_index=True
    )

    if not all_dividends.empty:
        all_dividends = (
            all_dividends.sort_values(["figi", "payment_date"])
            .drop_duplicates(
                subset=["figi", "payment_date"],
                keep="last",
            )
            .reset_index(drop=True)
        )

    return all_dividends
