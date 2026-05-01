import pandas as pd

from its.data_loader.t_invest_data_readers.dividents_reader import (
    _build_cache_rows,
    _write_cache,
    read_dividends_from_cache,
)


def test_empty_dividends_response_is_cached_as_covered_range(tmp_path) -> None:
    figi = "TCS10A0JR514"
    cache_path = tmp_path / "dividends.csv"
    start = pd.Timestamp("2010-05-05")
    end = pd.Timestamp("2026-05-01")

    _write_cache(
        _build_cache_rows(figi, pd.DataFrame(), start, end),
        cache_path=cache_path,
    )

    cached_dividends, missing_ranges = read_dividends_from_cache(
        [figi],
        start,
        end,
        cache_path=cache_path,
    )

    assert cached_dividends.empty
    assert missing_ranges == {figi: []}


def test_dividends_cache_uses_requested_range_not_payment_dates_for_coverage(
    tmp_path,
) -> None:
    figi = "figi-1"
    cache_path = tmp_path / "dividends.csv"
    start = pd.Timestamp("2020-01-01")
    end = pd.Timestamp("2020-12-31")
    dividends = pd.DataFrame(
        [
            {
                "figi": figi,
                "payment_date": pd.Timestamp("2020-06-01"),
                "last_buy_date": pd.Timestamp("2020-05-15"),
            }
        ]
    )

    _write_cache(
        _build_cache_rows(figi, dividends, start, end),
        cache_path=cache_path,
    )

    cached_dividends, missing_ranges = read_dividends_from_cache(
        [figi],
        start,
        end,
        cache_path=cache_path,
    )

    assert missing_ranges == {figi: []}
    assert len(cached_dividends) == 1
    assert cached_dividends.iloc[0]["payment_date"] == pd.Timestamp("2020-06-01")


def test_dividends_cache_reports_only_uncovered_requested_ranges(tmp_path) -> None:
    figi = "figi-1"
    cache_path = tmp_path / "dividends.csv"
    cached_start = pd.Timestamp("2020-03-01")
    cached_end = pd.Timestamp("2020-03-31")

    _write_cache(
        _build_cache_rows(figi, pd.DataFrame(), cached_start, cached_end),
        cache_path=cache_path,
    )

    _, missing_ranges = read_dividends_from_cache(
        [figi],
        pd.Timestamp("2020-02-01"),
        pd.Timestamp("2020-04-30"),
        cache_path=cache_path,
    )

    assert missing_ranges == {
        figi: [
            (pd.Timestamp("2020-02-01"), pd.Timestamp("2020-02-29")),
            (pd.Timestamp("2020-04-01"), pd.Timestamp("2020-04-30")),
        ]
    }
