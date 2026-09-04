from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import sklearn.utils.validation as skv

from its.strategies.core.types.selectors_types import Selectros


class EquityLiquiditySelector(Selectros):
    """Keep assets whose trailing mean daily ruble turnover is high enough.

    On each date the selector forms a point-in-time universe limited to the
    previous ``lookback_days`` trading sessions: an asset is retained only when
    its average daily ruble turnover over that window is at least
    ``min_avg_daily_turnover_rub``. Assets with insufficient history, incorrect
    candles or unsuitable instrument type (handled upstream so the candle input
    is already equities) are excluded. The result is exposed as ``to_keep_``, a
    boolean mask aligned with the input columns.
    """

    turnover_summary_: pd.DataFrame
    asset_names_: np.ndarray
    selected_assets_: np.ndarray
    source_as_of_: pd.Timestamp | None

    def __init__(
        self,
        asset_universe_prices: pd.DataFrame | None = None,
        lookback_days: int = 63,
        min_avg_daily_turnover_rub: float = 10_000_000,
        min_history_days: int = 63,
        time_column: str = "time",
        open_column: str = "open",
        high_column: str = "high",
        low_column: str = "low",
        close_column: str = "close",
        volume_column: str = "volume",
    ) -> None:
        self.asset_universe_prices = asset_universe_prices
        self.lookback_days = lookback_days
        self.min_avg_daily_turnover_rub = min_avg_daily_turnover_rub
        self.min_history_days = min_history_days
        self.time_column = time_column
        self.open_column = open_column
        self.high_column = high_column
        self.low_column = low_column
        self.close_column = close_column
        self.volume_column = volume_column

    def fit(self, X: Any, y: Any = None) -> EquityLiquiditySelector:
        """Fit the selector and store a mask aligned with the input columns."""
        self._validate_parameters()
        values = skv.validate_data(self, X, ensure_all_finite="allow-nan")
        asset_names = self._asset_names(values)
        if self.asset_universe_prices is None:
            raise ValueError("asset_universe_prices is required")

        candles = self._prepare_candles(self.asset_universe_prices)
        summary, source_as_of = self._build_turnover_summary(candles)
        selected_tickers = summary.loc[
            summary["mean_daily_turnover"] >= self.min_avg_daily_turnover_rub,
            "ticker",
        ].to_numpy(dtype=str)

        self.to_keep_ = np.isin(asset_names.astype(str), selected_tickers).astype(bool)
        self.asset_names_ = asset_names
        self.selected_assets_ = asset_names[self.to_keep_]
        self.turnover_summary_ = summary
        self.source_as_of_ = source_as_of
        return self

    def _validate_parameters(self) -> None:
        if self.lookback_days <= 0:
            raise ValueError("lookback_days must be positive")
        if self.min_avg_daily_turnover_rub < 0:
            raise ValueError("min_avg_daily_turnover_rub must be non-negative")
        if self.min_history_days <= 0:
            raise ValueError("min_history_days must be positive")
        if self.min_history_days > self.lookback_days:
            raise ValueError(
                "min_history_days must be less than or equal to lookback_days"
            )

    def _asset_names(self, values: np.ndarray) -> np.ndarray:
        if hasattr(self, "feature_names_in_"):
            return self.feature_names_in_.astype(str)
        return np.asarray(
            [f"asset_{index}" for index in range(values.shape[1])]
        ).astype(str)

    def _prepare_candles(self, prices: pd.DataFrame) -> pd.DataFrame:
        price_columns = [
            self.open_column,
            self.high_column,
            self.low_column,
            self.close_column,
        ]
        required_columns = {
            "ticker",
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
            candles[self.time_column],
            errors="coerce",
            utc=True,
        ).dt.tz_localize(None)

        for column in [*price_columns, self.volume_column]:
            candles[column] = pd.to_numeric(candles[column], errors="coerce")

        candles = candles.dropna(subset=list(required_columns))
        candles["ticker"] = candles["ticker"].astype(str)
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

        candles["trading_date"] = candles[self.time_column].dt.normalize()
        candles["bar_price"] = candles[price_columns].mean(axis=1)
        candles["bar_turnover"] = candles["bar_price"] * candles[self.volume_column]
        return candles

    def _build_turnover_summary(
        self, candles: pd.DataFrame
    ) -> tuple[pd.DataFrame, pd.Timestamp | None]:
        if candles.empty:
            return self._empty_summary(), None

        source_as_of = pd.Timestamp(candles[self.time_column].max())
        daily_turnover = candles.groupby(
            ["ticker", "trading_date"],
            as_index=False,
            sort=False,
        ).agg(
            daily_turnover=("bar_turnover", "sum"),
            bars=(self.time_column, "size"),
        )
        lookback_dates = (
            daily_turnover["trading_date"]
            .drop_duplicates()
            .sort_values()
            .tail(self.lookback_days)
        )
        recent = daily_turnover.loc[daily_turnover["trading_date"].isin(lookback_dates)]
        summary = (
            recent.groupby("ticker", as_index=False)
            .agg(
                mean_daily_turnover=("daily_turnover", "mean"),
                trading_days=("trading_date", "nunique"),
                first_trading_date=("trading_date", "min"),
                last_trading_date=("trading_date", "max"),
                bars=("bars", "sum"),
            )
            .loc[lambda frame: frame["trading_days"] >= self.min_history_days]
            .sort_values(
                ["mean_daily_turnover", "ticker"],
                ascending=[False, True],
                kind="mergesort",
            )
            .reset_index(drop=True)
        )
        summary["source_as_of"] = source_as_of
        summary["lookback_days"] = self.lookback_days
        return summary, source_as_of

    def _empty_summary(self) -> pd.DataFrame:
        return pd.DataFrame(
            columns=[
                "ticker",
                "mean_daily_turnover",
                "trading_days",
                "first_trading_date",
                "last_trading_date",
                "bars",
                "source_as_of",
                "lookback_days",
            ]
        )
