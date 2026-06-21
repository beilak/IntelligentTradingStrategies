from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import sklearn.utils.validation as skv

from its.strategies.core.types.signals_types import Siglans


class CloseBelowRecentMarkerSignal(Siglans):
    """Select assets whose latest close is below a recent high/close marker.

    The marker is the maximum value of ``marker`` over the last
    ``lookback_bars`` bars. An asset is selected when:

    ``latest_close <= marker_value * (1 - threshold_pct)``.

    For example, ``marker="high"`` and ``threshold_pct=0.1`` selects assets
    whose latest close is at least 10% below the recent high.
    """

    VALID_MARKERS = {"high", "close"}

    to_keep_: np.ndarray

    def __init__(
        self,
        marker: str = "high",
        lookback_bars: int = 20,
        threshold_pct: float = 0.1,
        asset_universe_prices: pd.DataFrame | None = None,
        ticker_column: str = "ticker",
        time_column: str = "time",
        close_column: str = "close",
        high_column: str = "high",
    ):
        self.marker = marker
        self.lookback_bars = lookback_bars
        self.threshold_pct = threshold_pct
        self.asset_universe_prices = asset_universe_prices
        self.ticker_column = ticker_column
        self.time_column = time_column
        self.close_column = close_column
        self.high_column = high_column

    def fit(
        self,
        X: Any,
        y: Any = None,
        asset_universe_prices: pd.DataFrame | None = None,
    ) -> "CloseBelowRecentMarkerSignal":
        self._validate_parameters()

        X_validated = skv.validate_data(self, X, ensure_all_finite="allow-nan")
        asset_names = self._asset_names(X_validated)
        prices = (
            asset_universe_prices
            if asset_universe_prices is not None
            else self.asset_universe_prices
        )

        if prices is None:
            close_values, marker_values, bars_used = self._fit_from_close_matrix(
                X_validated,
                asset_names,
            )
        else:
            close_values, marker_values, bars_used = self._fit_from_long_prices(
                prices,
                asset_names,
            )

        threshold_values = marker_values * (1.0 - self.threshold_pct)
        self.to_keep_ = (
            np.isfinite(close_values)
            & np.isfinite(marker_values)
            & (close_values > 0)
            & (marker_values > 0)
            & (bars_used >= self.lookback_bars)
            & (close_values <= threshold_values)
        )
        self.latest_close_ = pd.Series(close_values, index=asset_names)
        self.marker_values_ = pd.Series(marker_values, index=asset_names)
        self.threshold_values_ = pd.Series(threshold_values, index=asset_names)
        self.bars_used_ = pd.Series(bars_used, index=asset_names)
        return self

    def _validate_parameters(self) -> None:
        if self.marker not in self.VALID_MARKERS:
            raise ValueError(
                f"marker must be one of {sorted(self.VALID_MARKERS)}, got {self.marker!r}"
            )
        if self.lookback_bars <= 0:
            raise ValueError("lookback_bars must be positive")
        if not np.isfinite(self.threshold_pct) or not 0 <= self.threshold_pct < 1:
            raise ValueError("threshold_pct must be in the interval [0, 1)")

    def _fit_from_close_matrix(
        self,
        X: np.ndarray,
        asset_names: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        if self.marker != "close":
            raise ValueError("asset_universe_prices is required when marker='high'")
        n_samples, n_features = X.shape
        if n_samples < self.lookback_bars:
            raise ValueError(
                f"X must have at least {self.lookback_bars} samples, got {n_samples}"
            )

        recent = X[-self.lookback_bars :]
        close_values = X[-1].astype(float)
        marker_values = np.full(n_features, np.nan, dtype=float)
        valid_marker_columns = ~np.isnan(recent).all(axis=0)
        if valid_marker_columns.any():
            marker_values[valid_marker_columns] = np.nanmax(
                recent[:, valid_marker_columns],
                axis=0,
            )
        bars_used = np.full(n_features, self.lookback_bars, dtype=int)
        return close_values, marker_values, bars_used

    def _fit_from_long_prices(
        self,
        prices: pd.DataFrame,
        asset_names: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        marker_column = self.high_column if self.marker == "high" else self.close_column
        required_columns = {
            self.ticker_column,
            self.time_column,
            self.close_column,
            marker_column,
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
        )
        candles[self.close_column] = pd.to_numeric(
            candles[self.close_column],
            errors="coerce",
        )
        candles[marker_column] = pd.to_numeric(
            candles[marker_column],
            errors="coerce",
        )
        candles = candles.dropna(
            subset=[
                self.ticker_column,
                self.time_column,
                self.close_column,
                marker_column,
            ]
        )
        candles[self.ticker_column] = candles[self.ticker_column].astype(str)
        if "is_complete" in candles.columns:
            candles = candles.loc[candles["is_complete"].fillna(False)].copy()

        close_values = np.full(len(asset_names), np.nan, dtype=float)
        marker_values = np.full(len(asset_names), np.nan, dtype=float)
        bars_used = np.zeros(len(asset_names), dtype=int)
        if candles.empty:
            return close_values, marker_values, bars_used

        grouped = candles.sort_values([self.ticker_column, self.time_column]).groupby(
            self.ticker_column,
            sort=False,
        )
        for index, asset_name in enumerate(asset_names.astype(str)):
            if asset_name not in grouped.groups:
                continue
            recent = grouped.get_group(asset_name).tail(self.lookback_bars)
            bars_used[index] = len(recent)
            close_values[index] = float(recent[self.close_column].iloc[-1])
            marker_values[index] = float(recent[marker_column].max())
        return close_values, marker_values, bars_used

    def _asset_names(self, X: np.ndarray) -> np.ndarray:
        if hasattr(self, "feature_names_in_"):
            return self.feature_names_in_.astype(str)
        return np.asarray([f"asset_{i}" for i in range(X.shape[1])], dtype=str)
