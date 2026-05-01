import numpy as np
import pandas as pd

from its.strategies.core.selectors import (
    CrossSectionalMomentumSelector,
    DividendHistorySelector,
)


def test_cross_sectional_momentum_preserves_dataframe_columns() -> None:
    index = pd.bdate_range("2024-01-01", periods=6)
    prices = pd.DataFrame(
        {
            "FAST": [100, 102, 104, 106, 108, 110],
            "SLOW": [100, 100, 101, 101, 102, 102],
            "DOWN": [100, 99, 98, 97, 96, 95],
        },
        index=index,
    )

    selector = CrossSectionalMomentumSelector(
        lookback=3,
        quantile=0.5,
        min_periods=3,
    ).fit(prices)
    transformed = selector.transform(prices)

    assert isinstance(selector.to_keep_, np.ndarray)
    assert selector.to_keep_.dtype == bool
    assert list(transformed.columns) == ["FAST", "SLOW"]
    assert list(selector.get_momentum_scores().index) == ["FAST", "SLOW", "DOWN"]


def test_dividend_history_preserves_dataframe_columns() -> None:
    index = pd.bdate_range("2024-01-01", periods=3)
    prices = pd.DataFrame(
        {
            "DIV": [100, 101, 102],
            "ONE": [100, 101, 102],
            "NONE": [100, 101, 102],
        },
        index=index,
    )
    dividends = pd.DataFrame(
        {
            "ticker": ["DIV", "DIV", "ONE"],
            "last_buy_date": [
                "2022-03-01",
                "2023-03-01",
                "2023-03-01",
            ],
        }
    )

    selector = DividendHistorySelector(
        dividends_df=dividends,
        years=2,
    ).fit(prices)
    transformed = selector.transform(prices)

    assert isinstance(selector.to_keep_, np.ndarray)
    assert selector.to_keep_.dtype == bool
    assert list(transformed.columns) == ["DIV"]


def test_dividend_history_can_require_one_dividend_year() -> None:
    index = pd.bdate_range("2024-01-01", periods=3)
    prices = pd.DataFrame(
        {
            "DIV": [100, 101, 102],
            "ONE": [100, 101, 102],
        },
        index=index,
    )
    dividends = pd.DataFrame(
        {
            "ticker": ["DIV", "DIV", "ONE"],
            "last_buy_date": [
                pd.Timestamp("2022-03-01"),
                pd.Timestamp("2023-03-01"),
                pd.Timestamp("2023-03-01"),
            ],
        }
    )

    selector = DividendHistorySelector(
        dividends_df=dividends,
        years=2,
        min_dividend_years=1,
    ).fit(prices)
    transformed = selector.transform(prices)

    assert list(transformed.columns) == ["DIV", "ONE"]
