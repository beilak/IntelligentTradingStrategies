from __future__ import annotations

from typing import Any, ClassVar

import numpy as np
import pandas as pd
import sklearn.utils.validation as skv

from its.strategies.core.types.signals_types import Siglans


class ExtremumRangeLongSignal(Siglans):
    """Select long breakouts confirmed by a prior-bar EMA-side streak."""

    VALID_GATE_SIDES: ClassVar[set[str]] = {"above", "below", "either"}

    def __init__(
        self,
        asset_universe_prices: pd.DataFrame | None = None,
        channel_lookback_bars: int = 30,
        ema_length: int = 500,
        streak_length: int = 50,
        gate_side: str = "either",
        ticker_column: str = "ticker",
        time_column: str = "time",
        high_column: str = "high",
        close_column: str = "close",
    ) -> None:
        self.asset_universe_prices = asset_universe_prices
        self.channel_lookback_bars = channel_lookback_bars
        self.ema_length = ema_length
        self.streak_length = streak_length
        self.gate_side = gate_side
        self.ticker_column = ticker_column
        self.time_column = time_column
        self.high_column = high_column
        self.close_column = close_column

    def fit(self, X: Any, y: Any = None) -> ExtremumRangeLongSignal:
        """Fit the signal and store a mask aligned with the input columns."""
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
        required_bars = max(
            self.ema_length + self.streak_length + 1,
            self.channel_lookback_bars + 1,
        )
        n_assets = len(asset_names)
        channel_high = np.full(n_assets, np.nan)
        latest_close = np.full(n_assets, np.nan)
        latest_ema = np.full(n_assets, np.nan)
        bars_used = np.zeros(n_assets, dtype=int)
        above_streak = np.zeros(n_assets, dtype=bool)
        below_streak = np.zeros(n_assets, dtype=bool)
        gate_passed = np.zeros(n_assets, dtype=bool)
        streak_side = np.full(n_assets, "none", dtype=object)
        self.to_keep_ = np.zeros(n_assets, dtype=bool)

        grouped = candles.sort_values([self.ticker_column, self.time_column]).groupby(
            self.ticker_column,
            sort=False,
        )
        for index, asset_name in enumerate(asset_names):
            if asset_name not in grouped.groups:
                continue
            recent = grouped.get_group(asset_name).tail(required_bars)
            bars_used[index] = len(recent)
            if len(recent) < required_bars:
                continue

            closes = recent[self.close_column].to_numpy(dtype=float)
            highs = recent[self.high_column].to_numpy(dtype=float)
            ema = (
                pd.Series(closes)
                .ewm(
                    span=self.ema_length,
                    adjust=False,
                    min_periods=self.ema_length,
                )
                .mean()
                .to_numpy(dtype=float)
            )
            streak_slice = slice(-(self.streak_length + 1), -1)
            streak_closes = closes[streak_slice]
            streak_ema = ema[streak_slice]
            if not np.isfinite(streak_ema).all():
                continue

            above_streak[index] = bool(np.all(streak_closes > streak_ema))
            below_streak[index] = bool(np.all(streak_closes < streak_ema))
            if above_streak[index]:
                streak_side[index] = "above"
            elif below_streak[index]:
                streak_side[index] = "below"

            gate_passed[index] = self._gate_passed(
                above=above_streak[index],
                below=below_streak[index],
            )
            channel_high[index] = float(
                np.max(highs[-(self.channel_lookback_bars + 1) : -1])
            )
            latest_close[index] = float(closes[-1])
            latest_ema[index] = float(ema[-1])
            self.to_keep_[index] = bool(
                gate_passed[index] and latest_close[index] > channel_high[index]
            )

        self.asset_names_ = asset_names
        self.channel_high_ = pd.Series(channel_high, index=asset_names)
        self.latest_close_ = pd.Series(latest_close, index=asset_names)
        self.latest_ema_ = pd.Series(latest_ema, index=asset_names)
        self.above_streak_ = pd.Series(above_streak, index=asset_names)
        self.below_streak_ = pd.Series(below_streak, index=asset_names)
        self.gate_passed_ = pd.Series(gate_passed, index=asset_names)
        self.streak_side_ = pd.Series(streak_side, index=asset_names)
        self.bars_used_ = pd.Series(bars_used, index=asset_names)
        self.required_bars_ = required_bars
        return self

    def _validate_parameters(self) -> None:
        if self.channel_lookback_bars <= 0:
            raise ValueError("channel_lookback_bars must be positive")
        if self.ema_length <= 0:
            raise ValueError("ema_length must be positive")
        if self.streak_length <= 0:
            raise ValueError("streak_length must be positive")
        if self.gate_side not in self.VALID_GATE_SIDES:
            allowed = ", ".join(sorted(self.VALID_GATE_SIDES))
            raise ValueError(f"gate_side must be one of: {allowed}")

    def _prepare_candles(self, prices: pd.DataFrame) -> pd.DataFrame:
        required_columns = {
            self.ticker_column,
            self.time_column,
            self.high_column,
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
        for column in (self.high_column, self.close_column):
            candles[column] = pd.to_numeric(candles[column], errors="coerce")
        candles = candles.dropna(subset=list(required_columns))
        candles[self.ticker_column] = candles[self.ticker_column].astype(str)
        if "is_complete" in candles.columns:
            candles = candles.loc[candles["is_complete"].fillna(False)].copy()

        finite = np.isfinite(
            candles[[self.high_column, self.close_column]].to_numpy(dtype=float)
        ).all(axis=1)
        positive = (candles[[self.high_column, self.close_column]] > 0).all(axis=1)
        return candles.loc[finite & positive].copy()

    def _gate_passed(self, *, above: bool, below: bool) -> bool:
        if self.gate_side == "above":
            return above
        if self.gate_side == "below":
            return below
        return above or below
