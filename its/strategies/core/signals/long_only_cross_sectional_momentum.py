from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import sklearn.utils.validation as skv

from its.strategies.core.types.signals_types import Siglans


class LongOnlyCrossSectionalMomentumSignal(Siglans):
    """Select the top-N assets by classic medium-term cross-sectional momentum.

    On each date the signal computes for every asset the momentum of its
    adjusted close price over the previous ``lookback_days`` trading sessions,
    skipping the most recent ``skip_last_days`` sessions (Jegadeesh-Titman
    style). Assets are ranked by momentum in descending order and the top
    ``top_n`` are kept. The strategy is long-only: negative absolute momentum is
    not a reason for exclusion when the asset still ranks within the Top-N.
    """

    momentum_scores_: pd.Series
    ranking_: pd.Series
    selected_assets_: np.ndarray
    exclusion_reasons_: pd.Series
    formation_intervals_: pd.DataFrame
    formation_start_: pd.Timestamp | None
    formation_end_: pd.Timestamp | None

    def __init__(
        self,
        asset_universe_prices: pd.DataFrame | None = None,
        lookback_days: int = 252,
        skip_last_days: int = 21,
        top_n: int = 10,
        ticker_column: str = "ticker",
        time_column: str = "time",
        close_column: str = "close",
    ) -> None:
        self.asset_universe_prices = asset_universe_prices
        self.lookback_days = lookback_days
        self.skip_last_days = skip_last_days
        self.top_n = top_n
        self.ticker_column = ticker_column
        self.time_column = time_column
        self.close_column = close_column

    def fit(self, X: Any, y: Any = None) -> LongOnlyCrossSectionalMomentumSignal:
        """Fit the signal and store a mask aligned with the input columns."""
        self._validate_parameters()
        values = skv.validate_data(self, X, ensure_all_finite="allow-nan")
        asset_names = self._asset_names(values)
        if self.asset_universe_prices is None:
            raise ValueError("asset_universe_prices is required")

        candles = self._prepare_candles(self.asset_universe_prices)
        required = self.lookback_days + self.skip_last_days + 1
        n_assets = len(asset_names)
        momentum = np.full(n_assets, np.nan)
        reasons = np.full(n_assets, "", dtype=object)
        formation_start = np.full(n_assets, np.nan, dtype=object)
        formation_end = np.full(n_assets, np.nan, dtype=object)
        observations = np.zeros(n_assets, dtype=int)

        grouped = candles.sort_values([self.ticker_column, self.time_column]).groupby(
            self.ticker_column, sort=False
        )
        for index, asset_name in enumerate(asset_names):
            if asset_name not in grouped.groups:
                reasons[index] = "insufficient_history"
                continue
            recent = grouped.get_group(asset_name)
            observations[index] = len(recent)
            if len(recent) < required:
                reasons[index] = "insufficient_history"
                continue
            closes = recent[self.close_column].to_numpy(dtype=float)
            present = closes[-self.skip_last_days - 1]
            past = closes[-(self.skip_last_days + self.lookback_days) - 1]
            momentum[index] = float(present / past - 1.0)
            formation_start[index] = recent[self.time_column].iloc[
                -(self.skip_last_days + self.lookback_days) - 1
            ]
            formation_end[index] = recent[self.time_column].iloc[
                -self.skip_last_days - 1
            ]

        rank_table = pd.DataFrame(
            {
                "position": np.arange(n_assets),
                "ticker": asset_names.astype(str),
                "momentum": momentum,
            }
        )
        rankable = rank_table.loc[np.isfinite(momentum)].copy()
        order = rankable.sort_values(
            ["momentum", "ticker"],
            ascending=[False, True],
            kind="mergesort",
        )
        order["rank"] = np.arange(1, len(order) + 1)
        ranks = np.zeros(n_assets, dtype=int)
        for _, row in order.iterrows():
            position = int(row["position"])
            ranks[position] = int(row["rank"])
            if row["rank"] > self.top_n:
                reasons[position] = "below_top_n"

        self.to_keep_ = (ranks > 0) & (ranks <= self.top_n)
        self.momentum_scores_ = pd.Series(momentum, index=asset_names)
        self.ranking_ = pd.Series(ranks, index=asset_names)
        self.selected_assets_ = asset_names[self.to_keep_]
        self.observations_used_ = pd.Series(observations, index=asset_names)
        self.required_observations_ = required
        self.exclusion_reasons_ = pd.Series(reasons, index=asset_names)
        self.formation_intervals_ = self._build_formation_intervals(
            asset_names, formation_start, formation_end
        )
        starts = pd.to_datetime(pd.Series(formation_start, dtype="object").dropna())
        ends = pd.to_datetime(pd.Series(formation_end, dtype="object").dropna())
        self.formation_start_ = pd.Timestamp(starts.min()) if not starts.empty else None
        self.formation_end_ = pd.Timestamp(ends.max()) if not ends.empty else None
        return self

    def _validate_parameters(self) -> None:
        if self.lookback_days <= 0:
            raise ValueError("lookback_days must be positive")
        if self.skip_last_days < 0:
            raise ValueError("skip_last_days must be non-negative")
        if self.top_n <= 0:
            raise ValueError("top_n must be positive")

    def _asset_names(self, values: np.ndarray) -> np.ndarray:
        if hasattr(self, "feature_names_in_"):
            return self.feature_names_in_.astype(str)
        return np.asarray(
            [f"asset_{index}" for index in range(values.shape[1])]
        ).astype(str)

    def _prepare_candles(self, prices: pd.DataFrame) -> pd.DataFrame:
        required_columns = {
            self.ticker_column,
            self.time_column,
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
            candles[self.time_column],
            errors="coerce",
            utc=True,
        ).dt.tz_localize(None)

        candles[self.close_column] = pd.to_numeric(
            candles[self.close_column], errors="coerce"
        )
        candles = candles.dropna(subset=list(required_columns))
        candles[self.ticker_column] = candles[self.ticker_column].astype(str)
        if "is_complete" in candles.columns:
            candles = candles.loc[candles["is_complete"].fillna(False)].copy()

        close = candles[self.close_column].to_numpy(dtype=float)
        finite = np.isfinite(close)
        positive = close > 0
        return candles.loc[finite & positive].copy()

    def _build_formation_intervals(
        self,
        asset_names: np.ndarray,
        formation_start: np.ndarray,
        formation_end: np.ndarray,
    ) -> pd.DataFrame:
        rows = []
        starts = pd.to_datetime(pd.Series(formation_start, dtype="object"))
        ends = pd.to_datetime(pd.Series(formation_end, dtype="object"))
        for index, asset_name in enumerate(asset_names):
            if pd.isna(starts.iloc[index]):
                continue
            rows.append(
                {
                    "ticker": asset_name,
                    "formation_start": starts.iloc[index],
                    "formation_end": ends.iloc[index],
                }
            )
        return pd.DataFrame(
            rows, columns=["ticker", "formation_start", "formation_end"]
        )
