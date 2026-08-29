from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import sklearn.utils.validation as skv

from its.strategies.core.types.selectors_types import Selectros


class QuarterlyTopTurnoverSelector(Selectros):
    """Select the top-N assets by trailing mean daily ruble turnover.

    Membership is calculated from the previous completed calendar quarter and
    therefore stays unchanged inside the current quarter. Intraday candle
    turnover is aggregated to daily turnover before ranking.
    """

    def __init__(
        self,
        asset_universe_prices: pd.DataFrame | None = None,
        top_n: int = 40,
        lookback_days: int = 252,
        min_history_days: int = 252,
        ticker_column: str = "ticker",
        time_column: str = "time",
        open_column: str = "open",
        high_column: str = "high",
        low_column: str = "low",
        close_column: str = "close",
        volume_column: str = "volume",
    ) -> None:
        self.asset_universe_prices = asset_universe_prices
        self.top_n = top_n
        self.lookback_days = lookback_days
        self.min_history_days = min_history_days
        self.ticker_column = ticker_column
        self.time_column = time_column
        self.open_column = open_column
        self.high_column = high_column
        self.low_column = low_column
        self.close_column = close_column
        self.volume_column = volume_column

    def fit(self, X: Any, y: Any = None) -> QuarterlyTopTurnoverSelector:
        """Fit the selector and store a mask aligned with the input columns."""
        self._validate_parameters()
        values = skv.validate_data(self, X, ensure_all_finite="allow-nan")
        asset_names = (
            self.feature_names_in_.astype(str)
            if hasattr(self, "feature_names_in_")
            else np.asarray([f"asset_{index}" for index in range(values.shape[1])])
        )
        if self.asset_universe_prices is None:
            raise ValueError("asset_universe_prices is required")

        candles = self._prepare_candles(self.asset_universe_prices)
        summary, source_as_of, ranking_date = self._build_turnover_summary(candles)
        selected_tickers = summary.head(self.top_n)[self.ticker_column].to_numpy(
            dtype=str
        )

        self.to_keep_ = np.isin(asset_names, selected_tickers).astype(bool)
        self.asset_names_ = asset_names
        self.selected_assets_ = asset_names[self.to_keep_]
        self.turnover_summary_ = summary
        self.source_as_of_ = source_as_of
        self.ranking_date_ = ranking_date
        return self

    def _validate_parameters(self) -> None:
        if self.top_n <= 0:
            raise ValueError("top_n must be positive")
        if self.lookback_days <= 0:
            raise ValueError("lookback_days must be positive")
        if self.min_history_days <= 0:
            raise ValueError("min_history_days must be positive")
        if self.min_history_days > self.lookback_days:
            raise ValueError(
                "min_history_days must be less than or equal to lookback_days"
            )

    def _prepare_candles(self, prices: pd.DataFrame) -> pd.DataFrame:
        price_columns = [
            self.open_column,
            self.high_column,
            self.low_column,
            self.close_column,
        ]
        required_columns = {
            self.ticker_column,
            self.time_column,
            self.volume_column,
            *price_columns,
        }
        missing_columns = required_columns.difference(prices.columns)
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise ValueError(
                f"asset_universe_prices is missing required columns: {missing}"
            )

        candles = prices.copy()
        candles[self.time_column] = pd.to_datetime(
            candles[self.time_column], errors="coerce"
        )
        if candles[self.time_column].dt.tz is not None:
            candles[self.time_column] = candles[self.time_column].dt.tz_localize(None)
        for column in [*price_columns, self.volume_column]:
            candles[column] = pd.to_numeric(candles[column], errors="coerce")

        candles = candles.dropna(subset=list(required_columns))
        candles[self.ticker_column] = candles[self.ticker_column].astype(str)
        if "is_complete" in candles.columns:
            candles = candles.loc[candles["is_complete"].fillna(False)].copy()

        finite = np.isfinite(
            candles[[*price_columns, self.volume_column]].to_numpy(dtype=float)
        ).all(axis=1)
        positive_prices = (candles[price_columns] > 0).all(axis=1)
        non_negative_volume = candles[self.volume_column] >= 0
        candles = candles.loc[finite & positive_prices & non_negative_volume].copy()
        if candles.empty:
            return candles

        candles["_trading_date"] = candles[self.time_column].dt.normalize()
        candles["_bar_price"] = candles[price_columns].mean(axis=1)
        candles["_bar_turnover"] = candles["_bar_price"] * candles[self.volume_column]
        return candles

    def _build_turnover_summary(
        self, candles: pd.DataFrame
    ) -> tuple[pd.DataFrame, pd.Timestamp | None, pd.Timestamp | None]:
        if candles.empty:
            return self._empty_summary(), None, None

        source_as_of = pd.Timestamp(candles[self.time_column].max())
        previous_quarter_end = (source_as_of.to_period("Q") - 1).end_time.normalize()
        daily_turnover = (
            candles.groupby(
                [self.ticker_column, "_trading_date"],
                as_index=False,
                sort=False,
            )
            .agg(
                daily_turnover=("_bar_turnover", "sum"),
                bars=(self.time_column, "size"),
            )
            .loc[lambda frame: frame["_trading_date"] <= previous_quarter_end]
        )
        if daily_turnover.empty:
            return self._empty_summary(), source_as_of, None

        ranking_date = pd.Timestamp(daily_turnover["_trading_date"].max())
        lookback_dates = (
            daily_turnover["_trading_date"]
            .drop_duplicates()
            .sort_values()
            .tail(self.lookback_days)
        )
        recent = daily_turnover.loc[
            daily_turnover["_trading_date"].isin(lookback_dates)
        ]
        summary = (
            recent.groupby(self.ticker_column, as_index=False)
            .agg(
                mean_daily_turnover=("daily_turnover", "mean"),
                trading_days=("_trading_date", "nunique"),
                first_trading_date=("_trading_date", "min"),
                last_trading_date=("_trading_date", "max"),
                bars=("bars", "sum"),
            )
            .loc[lambda frame: frame["trading_days"] >= self.min_history_days]
            .sort_values(
                ["mean_daily_turnover", self.ticker_column],
                ascending=[False, True],
                kind="mergesort",
            )
            .reset_index(drop=True)
        )
        summary["rank"] = np.arange(1, len(summary) + 1)
        summary["ranking_date"] = ranking_date
        summary["lookback_days"] = self.lookback_days
        return summary, source_as_of, ranking_date

    def _empty_summary(self) -> pd.DataFrame:
        return pd.DataFrame(
            columns=[
                self.ticker_column,
                "mean_daily_turnover",
                "trading_days",
                "first_trading_date",
                "last_trading_date",
                "bars",
                "rank",
                "ranking_date",
                "lookback_days",
            ]
        )
