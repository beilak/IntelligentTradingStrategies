import numpy as np
import pandas as pd
from sklearn.utils.validation import validate_data

from its.strategies.core.types.selectors_types import Selectros


class DividendHistorySelector(Selectros):
    """
    Select assets that have paid dividends in each of the last N years
    before the last train date.

    Parameters
    ----------
    dividends_df : pd.DataFrame
        Columns: ['last_buy_date', 'ticker']
        Each row represents a dividend event.
    years : int
        Number of past years required.
    min_dividend_years : int | None
        Minimum number of distinct dividend years required in the lookback window.
        Defaults to ``years``.
    """

    def __init__(
        self,
        dividends_df: pd.DataFrame,
        years: int = 3,
        min_dividend_years: int | None = None,
    ):
        self.dividends_df = dividends_df
        self.years = years
        self.min_dividend_years = min_dividend_years

    def fit(self, X: pd.DataFrame, y=None):
        if not isinstance(X, pd.DataFrame):
            raise ValueError("X must be DataFrame")
        if X.empty:
            raise ValueError("X is empty")
        if self.years <= 0:
            raise ValueError("years must be positive")

        required_years = (
            self.years if self.min_dividend_years is None else self.min_dividend_years
        )
        if required_years <= 0:
            raise ValueError("min_dividend_years must be positive")
        if required_years > self.years:
            raise ValueError("min_dividend_years must be less than or equal to years")

        validate_data(
            self,
            X,
            accept_sparse=False,
            dtype=None,
            ensure_all_finite="allow-nan",
            reset=True,
        )
        dividends = self._validate_dividends()

        current_date = pd.to_datetime(X.index[-1])

        # ----  определяем границу по времени
        start_date = pd.to_datetime(current_date) - pd.DateOffset(years=self.years)

        # ---- берём дивиденды только до текущей даты (no look-ahead)
        df = dividends.copy()
        df = df[df["last_buy_date"] <= current_date]
        df = df[df["last_buy_date"] >= start_date]

        if df.empty:
            # никто не платил — возвращаем пустую маску
            self.to_keep_ = np.zeros(len(X.columns), dtype=bool)
            return self

        # ----  считаем годы выплат
        df["year"] = df["last_buy_date"].dt.year

        # группируем по тикеру и считаем уникальные годы
        counts = df.groupby("ticker")["year"].nunique()

        # ---- оставляем только те, где число лет >= required_years
        eligible_tickers = counts[counts >= required_years].index

        # ---- формируем mask
        mask = pd.Series(False, index=X.columns)
        mask.loc[mask.index.intersection(eligible_tickers)] = True

        self.to_keep_ = mask.values

        return self

    def _validate_dividends(self) -> pd.DataFrame:
        if not isinstance(self.dividends_df, pd.DataFrame):
            raise ValueError("dividends_df must be DataFrame")

        required_columns = {"last_buy_date", "ticker"}
        missing_columns = required_columns.difference(self.dividends_df.columns)
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise ValueError(f"dividends_df is missing required columns: {missing}")

        dividends = self.dividends_df.loc[:, ["last_buy_date", "ticker"]].copy()
        dividends["last_buy_date"] = pd.to_datetime(
            dividends["last_buy_date"],
            errors="coerce",
        )
        dividends = dividends.dropna(subset=["last_buy_date", "ticker"])
        dividends["ticker"] = dividends["ticker"].astype(str)
        return dividends
