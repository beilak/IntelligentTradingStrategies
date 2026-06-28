from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import sklearn.utils.validation as skv

from its.strategies.core.types.signals_types import Siglans


class RangeLowProximitySignal(Siglans):
    """Select assets with a wide recent range and a close near its low."""

    to_keep_: np.ndarray

    def __init__(
        self,
        lookback_bars: int = 20,
        min_range_pct: float = 0.10,
        max_close_to_low_pct: float = 0.03,
        asset_universe_prices: pd.DataFrame | None = None,
        ticker_column: str = "ticker",
        time_column: str = "time",
        close_column: str = "close",
        high_column: str = "high",
        low_column: str = "low",
    ):
        self.lookback_bars = lookback_bars
        self.min_range_pct = min_range_pct
        self.max_close_to_low_pct = max_close_to_low_pct
        self.asset_universe_prices = asset_universe_prices
        self.ticker_column = ticker_column
        self.time_column = time_column
        self.close_column = close_column
        self.high_column = high_column
        self.low_column = low_column

    def fit(self, X: Any, y: Any = None) -> "RangeLowProximitySignal":
        self._validate_parameters()
        X_validated = skv.validate_data(self, X, ensure_all_finite="allow-nan")
        asset_names = (
            self.feature_names_in_.astype(str)
            if hasattr(self, "feature_names_in_")
            else np.asarray([f"asset_{index}" for index in range(X_validated.shape[1])])
        )
        prices = self.asset_universe_prices
        if prices is None:
            raise ValueError("asset_universe_prices is required")

        required = {
            self.ticker_column,
            self.time_column,
            self.close_column,
            self.high_column,
            self.low_column,
        }
        missing = required.difference(prices.columns)
        if missing:
            raise ValueError(
                "asset_universe_prices is missing required columns: "
                + ", ".join(sorted(missing))
            )

        candles = prices.copy()
        candles[self.time_column] = pd.to_datetime(
            candles[self.time_column], errors="coerce"
        )
        for column in (self.close_column, self.high_column, self.low_column):
            candles[column] = pd.to_numeric(candles[column], errors="coerce")
        candles = candles.dropna(subset=list(required))
        candles[self.ticker_column] = candles[self.ticker_column].astype(str)
        if "is_complete" in candles.columns:
            candles = candles.loc[candles["is_complete"].fillna(False)]

        range_pct = np.full(len(asset_names), np.nan)
        close_to_low_pct = np.full(len(asset_names), np.nan)
        bars_used = np.zeros(len(asset_names), dtype=int)
        grouped = candles.sort_values([self.ticker_column, self.time_column]).groupby(
            self.ticker_column, sort=False
        )
        for index, asset_name in enumerate(asset_names):
            if asset_name not in grouped.groups:
                continue
            recent = grouped.get_group(asset_name).tail(self.lookback_bars)
            bars_used[index] = len(recent)
            if len(recent) < self.lookback_bars:
                continue
            lowest_low = float(recent[self.low_column].min())
            highest_high = float(recent[self.high_column].max())
            current_close = float(recent[self.close_column].iloc[-1])
            if not np.isfinite(lowest_low) or lowest_low <= 0:
                continue
            range_pct[index] = (highest_high - lowest_low) / lowest_low
            close_to_low_pct[index] = (current_close - lowest_low) / lowest_low

        self.to_keep_ = (
            np.isfinite(range_pct)
            & np.isfinite(close_to_low_pct)
            & (bars_used >= self.lookback_bars)
            & (range_pct >= self.min_range_pct)
            & (close_to_low_pct >= 0)
            & (close_to_low_pct <= self.max_close_to_low_pct)
        )
        self.range_pct_ = pd.Series(range_pct, index=asset_names)
        self.close_to_low_pct_ = pd.Series(close_to_low_pct, index=asset_names)
        self.bars_used_ = pd.Series(bars_used, index=asset_names)
        return self

    def _validate_parameters(self) -> None:
        if self.lookback_bars <= 0:
            raise ValueError("lookback_bars must be positive")
        if not np.isfinite(self.min_range_pct) or self.min_range_pct < 0:
            raise ValueError("min_range_pct must be finite and non-negative")
        if not np.isfinite(self.max_close_to_low_pct) or self.max_close_to_low_pct < 0:
            raise ValueError("max_close_to_low_pct must be finite and non-negative")
