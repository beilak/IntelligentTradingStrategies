from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import sklearn.base as skb
import sklearn.feature_selection as skf
import sklearn.utils.validation as skv
from skfolio.typing import ArrayLike, BoolArray

from its.strategies.core.types.dataframe_selector_mixin import DataFrameSelectorMixin


class IntradayTurnoverSelector(
    DataFrameSelectorMixin, skf.SelectorMixin, skb.BaseEstimator
):
    """Select assets by recent intraday ruble turnover.

    The selector is fitted on a wide returns/prices matrix where columns are asset
    tickers. Ruble turnover is calculated from the long intraday candle table passed
    through ``asset_universe_prices``.
    """

    turnover_summary_: pd.DataFrame
    selected_assets_: np.ndarray
    to_keep_: BoolArray

    def __init__(
        self,
        asset_universe_prices: pd.DataFrame | None = None,
        lookback_bars: int = 100,
        min_turnover: float = 0.0,
        ticker_column: str = "ticker",
        time_column: str = "time",
        volume_column: str = "volume",
        allow_empty_selection: bool = False,
    ):
        self.asset_universe_prices = asset_universe_prices
        self.lookback_bars = lookback_bars
        self.min_turnover = min_turnover
        self.ticker_column = ticker_column
        self.time_column = time_column
        self.volume_column = volume_column
        self.allow_empty_selection = allow_empty_selection

    def fit(
        self,
        X: ArrayLike,
        y: Any = None,
        asset_universe_prices: pd.DataFrame | None = None,
    ) -> "IntradayTurnoverSelector":
        """Fit the selector and identify assets passing the turnover threshold."""
        X = skv.validate_data(self, X, ensure_all_finite="allow-nan")
        prices = (
            asset_universe_prices
            if asset_universe_prices is not None
            else self.asset_universe_prices
        )
        if prices is None:
            raise ValueError(
                "`asset_universe_prices` must be provided to the constructor or fit."
            )
        if self.lookback_bars <= 0:
            raise ValueError("lookback_bars must be positive")
        if self.min_turnover < 0:
            raise ValueError("min_turnover must be non-negative")

        turnover_summary = self._build_turnover_summary(prices)
        asset_names = self._asset_names(X)
        selected_tickers = (
            turnover_summary.loc[
                turnover_summary["turnover"] >= self.min_turnover, self.ticker_column
            ]
            .astype(str)
            .to_numpy()
        )
        self.to_keep_ = np.isin(asset_names.astype(str), selected_tickers)
        self.turnover_summary_ = turnover_summary
        self.selected_assets_ = asset_names[self.to_keep_]

        if not self.to_keep_.any() and not self.allow_empty_selection:
            raise ValueError(
                "Intraday turnover selector selected no assets present in X. "
                "Check the turnover threshold and that X columns are ticker names."
            )

        return self

    # def transform(self, X: ArrayLike) -> ArrayLike:
    #     """Reduce X to selected assets while preserving DataFrame column names."""
    #     skv.check_is_fitted(self)
    #     if hasattr(X, "iloc"):
    #         skv.validate_data(self, X, ensure_all_finite="allow-nan", reset=False)
    #         return X.iloc[:, self.to_keep_]

    #     X = skv.validate_data(self, X, ensure_all_finite="allow-nan", reset=False)
    #     return X[:, self.to_keep_]

    def _get_support_mask(self) -> BoolArray:
        skv.check_is_fitted(self)
        return self.to_keep_

    def __sklearn_tags__(self):
        tags = super().__sklearn_tags__()
        tags.input_tags.allow_nan = True
        return tags

    def _build_turnover_summary(self, prices: pd.DataFrame) -> pd.DataFrame:
        required_columns = {
            self.ticker_column,
            self.time_column,
            self.volume_column,
        }
        missing_columns = required_columns.difference(prices.columns)
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise ValueError(
                f"asset_universe_prices is missing required columns: {missing}"
            )

        price_columns = [
            column
            for column in ("open", "high", "low", "close")
            if column in prices.columns
        ]
        if not price_columns:
            raise ValueError(
                "asset_universe_prices must contain at least one price column: "
                "'open', 'high', 'low', or 'close'."
            )

        candles = prices.copy()
        candles[self.time_column] = pd.to_datetime(
            candles[self.time_column], errors="coerce"
        )
        candles[self.volume_column] = pd.to_numeric(
            candles[self.volume_column], errors="coerce"
        )
        for column in price_columns:
            candles[column] = pd.to_numeric(candles[column], errors="coerce")

        valid_mask = (
            candles[self.time_column].notna()
            & candles[self.ticker_column].notna()
            & candles[self.volume_column].notna()
        )
        for column in price_columns:
            valid_mask = valid_mask & candles[column].notna()

        candles = candles.loc[valid_mask].copy()
        if "is_complete" in candles.columns:
            candles = candles.loc[candles["is_complete"].fillna(False)].copy()

        if candles.empty:
            return pd.DataFrame(
                columns=[
                    self.ticker_column,
                    "turnover",
                    "bars",
                    "last_bar_time",
                    "lookback_bars_used",
                ]
            )

        candles["bar_price"] = candles[price_columns].mean(axis=1)
        candles["bar_turnover"] = candles["bar_price"] * candles[self.volume_column]
        recent_candles = (
            candles.sort_values([self.ticker_column, self.time_column])
            .groupby(self.ticker_column, group_keys=False)
            .tail(self.lookback_bars)
        )

        summary = (
            recent_candles.groupby(self.ticker_column, as_index=False)
            .agg(
                turnover=("bar_turnover", "sum"),
                bars=(self.time_column, "size"),
                last_bar_time=(self.time_column, "max"),
            )
            .sort_values("turnover", ascending=False)
            .reset_index(drop=True)
        )
        summary["lookback_bars_used"] = self.lookback_bars
        return summary

    def _asset_names(self, X: np.ndarray) -> np.ndarray:
        if hasattr(self, "feature_names_in_"):
            return self.feature_names_in_
        return np.arange(X.shape[1]).astype(str)


__all__ = ["IntradayTurnoverSelector"]
