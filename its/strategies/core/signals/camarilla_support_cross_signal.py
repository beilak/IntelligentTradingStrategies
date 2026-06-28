from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import sklearn.utils.validation as skv

from its.strategies.core.types.signals_types import Siglans


class CamarillaSupportCrossSignal(Siglans):
    """Select assets whose close crosses a Camarilla support from below.

    The support level is calculated from the reference candle at ``t-2``.
    A signal is emitted when ``close(t-1) < support <= close(t)``.
    """

    SUPPORT_DIVISORS = {"S1": 12.0, "S2": 6.0, "S3": 4.0, "S4": 2.0}
    to_keep_: np.ndarray

    def __init__(
        self,
        support_line: str = "S1",
        camarilla_multiplier: float = 1.1,
        asset_universe_prices: pd.DataFrame | None = None,
        ticker_column: str = "ticker",
        time_column: str = "time",
        high_column: str = "high",
        low_column: str = "low",
        close_column: str = "close",
    ):
        self.support_line = support_line
        self.camarilla_multiplier = camarilla_multiplier
        self.asset_universe_prices = asset_universe_prices
        self.ticker_column = ticker_column
        self.time_column = time_column
        self.high_column = high_column
        self.low_column = low_column
        self.close_column = close_column

    def fit(self, X: Any, y: Any = None) -> "CamarillaSupportCrossSignal":
        self._validate_parameters()
        values = skv.validate_data(self, X, ensure_all_finite="allow-nan")
        asset_names = (
            self.feature_names_in_.astype(str)
            if hasattr(self, "feature_names_in_")
            else np.asarray([f"asset_{index}" for index in range(values.shape[1])])
        )
        prices = self.asset_universe_prices
        if prices is None:
            raise ValueError("asset_universe_prices is required")

        required_columns = {
            self.ticker_column,
            self.time_column,
            self.high_column,
            self.low_column,
            self.close_column,
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
        for column in (self.high_column, self.low_column, self.close_column):
            candles[column] = pd.to_numeric(candles[column], errors="coerce")
        candles = candles.dropna(subset=list(required_columns))
        candles[self.ticker_column] = candles[self.ticker_column].astype(str)
        if "is_complete" in candles.columns:
            candles = candles.loc[candles["is_complete"].fillna(False)].copy()

        support_line = self.support_line.upper()
        support_levels = np.full((len(asset_names), 4), np.nan)
        previous_closes = np.full(len(asset_names), np.nan)
        current_closes = np.full(len(asset_names), np.nan)
        bars_used = np.zeros(len(asset_names), dtype=int)
        grouped = candles.sort_values([self.ticker_column, self.time_column]).groupby(
            self.ticker_column, sort=False
        )
        for index, asset_name in enumerate(asset_names):
            if asset_name not in grouped.groups:
                continue
            recent = grouped.get_group(asset_name).tail(3)
            bars_used[index] = len(recent)
            if len(recent) < 3:
                continue
            reference = recent.iloc[0]
            price_range = float(reference[self.high_column]) - float(
                reference[self.low_column]
            )
            reference_close = float(reference[self.close_column])
            if (
                not np.isfinite(price_range)
                or price_range < 0
                or not np.isfinite(reference_close)
                or reference_close <= 0
            ):
                continue
            support_levels[index] = [
                reference_close
                - self.camarilla_multiplier * price_range / self.SUPPORT_DIVISORS[line]
                for line in self.SUPPORT_DIVISORS
            ]
            previous_closes[index] = float(recent[self.close_column].iloc[1])
            current_closes[index] = float(recent[self.close_column].iloc[2])

        level_index = list(self.SUPPORT_DIVISORS).index(support_line)
        selected_levels = support_levels[:, level_index]
        self.to_keep_ = (
            np.isfinite(selected_levels)
            & np.isfinite(previous_closes)
            & np.isfinite(current_closes)
            & (previous_closes < selected_levels)
            & (current_closes >= selected_levels)
        )
        self.selected_support_line_ = support_line
        self.support_levels_ = pd.DataFrame(
            support_levels,
            index=asset_names,
            columns=list(self.SUPPORT_DIVISORS),
        )
        self.selected_levels_ = pd.Series(selected_levels, index=asset_names)
        self.previous_closes_ = pd.Series(previous_closes, index=asset_names)
        self.current_closes_ = pd.Series(current_closes, index=asset_names)
        self.bars_used_ = pd.Series(bars_used, index=asset_names)
        return self

    def _validate_parameters(self) -> None:
        if not isinstance(self.support_line, str) or (
            self.support_line.upper() not in self.SUPPORT_DIVISORS
        ):
            allowed = ", ".join(self.SUPPORT_DIVISORS)
            raise ValueError(f"support_line must be one of: {allowed}")
        if not np.isfinite(self.camarilla_multiplier) or self.camarilla_multiplier <= 0:
            raise ValueError("camarilla_multiplier must be finite and positive")
