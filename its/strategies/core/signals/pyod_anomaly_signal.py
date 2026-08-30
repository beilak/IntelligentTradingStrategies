from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import sklearn.utils.validation as skv
from pyod.models.ecod import ECOD
from sklearn.base import clone

from its.strategies.core.types.signals_types import Siglans

VALID_DIRECTIONS = {"positive", "negative", "either"}

FEATURE_TO_COLUMNS: dict[str, tuple[str, ...]] = {
    "return": ("close",),
    "intraday_range": ("high", "low", "close"),
    "volume_change": ("volume",),
}


class PyODAnomalySignal(Siglans):
    """Select assets whose latest bar is a PyOD-detected price anomaly.

    For every asset a per-bar feature matrix is built from ``asset_universe_prices``
    over the last ``lookback_bars`` complete candles and a fresh clone of the
    configured detector is fitted on it. An asset is selected when the latest bar is
    scored as an anomaly by the detector and its direction satisfies ``direction``:
    ``"positive"`` requires a positive latest return, ``"negative"`` a negative one,
    ``"either"`` accepts both. Assets with too little history or non-finite features
    are dropped from the selection.
    """

    VALID_FEATURES = set(FEATURE_TO_COLUMNS)

    to_keep_: np.ndarray

    def __init__(
        self,
        lookback_bars: int = 60,
        direction: str = "positive",
        detector: Any = None,
        feature_columns: tuple[str, ...] = ("return", "intraday_range", "volume_change"),
        asset_universe_prices: pd.DataFrame | None = None,
        ticker_column: str = "ticker",
        time_column: str = "time",
        close_column: str = "close",
        high_column: str = "high",
        low_column: str = "low",
        volume_column: str = "volume",
    ):
        self.lookback_bars = lookback_bars
        self.direction = direction
        self.detector = detector
        self.feature_columns = feature_columns
        self.asset_universe_prices = asset_universe_prices
        self.ticker_column = ticker_column
        self.time_column = time_column
        self.close_column = close_column
        self.high_column = high_column
        self.low_column = low_column
        self.volume_column = volume_column

    def fit(
        self,
        X: Any,
        y: Any = None,
        asset_universe_prices: pd.DataFrame | None = None,
    ) -> "PyODAnomalySignal":
        self._validate_parameters()

        X_validated = skv.validate_data(self, X, ensure_all_finite="allow-nan")
        asset_names = (
            self.feature_names_in_.astype(str)
            if hasattr(self, "feature_names_in_")
            else np.asarray([f"asset_{index}" for index in range(X_validated.shape[1])])
        )
        prices = (
            asset_universe_prices
            if asset_universe_prices is not None
            else self.asset_universe_prices
        )
        if prices is None:
            raise ValueError("asset_universe_prices is required")

        features_by_asset = self._build_features(prices, asset_names)

        scores = np.full(len(asset_names), np.nan)
        labels = np.zeros(len(asset_names), dtype=bool)
        latest_returns = np.full(len(asset_names), np.nan)
        bars_used = np.zeros(len(asset_names), dtype=int)
        fitted_detectors: dict[str, Any] = {}
        detector_template = clone(self._resolved_detector())

        for index, asset_name in enumerate(asset_names):
            features, bars, latest_return = features_by_asset[index]
            latest_returns[index] = latest_return
            bars_used[index] = bars
            if bars < self.lookback_bars:
                continue
            try:
                fitted = clone(detector_template)
                fitted.fit(features)
                score = self._score_latest(fitted)
            except (ValueError, FloatingPointError, np.linalg.LinAlgError):
                continue
            scores[index] = score
            labels[index] = self._is_anomaly(fitted, score)
            fitted_detectors[str(asset_name)] = fitted

        direction_ok = self._direction_ok(latest_returns)
        self.to_keep_ = labels & direction_ok & np.isfinite(scores)
        self.scores_ = pd.Series(scores, index=asset_names)
        self.labels_ = pd.Series(labels, index=asset_names)
        self.latest_return_ = pd.Series(latest_returns, index=asset_names)
        self.bars_used_ = pd.Series(bars_used, index=asset_names)
        self.fitted_detectors_ = fitted_detectors
        return self

    def _resolved_detector(self) -> Any:
        if self.detector is None:
            return ECOD(contamination=0.1)
        return self.detector

    @staticmethod
    def _score_latest(detector: Any) -> float:
        return float(detector.decision_scores_[-1])

    @staticmethod
    def _is_anomaly(detector: Any, score: float) -> bool:
        threshold = getattr(detector, "threshold_", None)
        if threshold is not None:
            return bool(score > threshold)
        return bool(getattr(detector, "labels_", [0])[-1] == 1)

    def _direction_ok(self, latest_returns: np.ndarray) -> np.ndarray:
        if self.direction == "positive":
            return latest_returns > 0
        if self.direction == "negative":
            return latest_returns < 0
        return np.ones(len(latest_returns), dtype=bool)

    def _build_features(
        self,
        prices: pd.DataFrame,
        asset_names: np.ndarray,
    ) -> list[tuple[pd.DataFrame, int, float]]:
        required_columns = {
            self.ticker_column,
            self.time_column,
        } | {
            column
            for feature in self.feature_columns
            for column in FEATURE_TO_COLUMNS[feature]
        }
        missing = required_columns.difference(prices.columns)
        if missing:
            raise ValueError(
                "asset_universe_prices is missing required columns: "
                + ", ".join(sorted(missing))
            )

        candles = prices.copy()
        candles[self.time_column] = pd.to_datetime(
            candles[self.time_column], errors="coerce"
        )
        for column in required_columns - {self.ticker_column, self.time_column}:
            candles[column] = pd.to_numeric(candles[column], errors="coerce")
        candles = candles.dropna(subset=required_columns)
        candles[self.ticker_column] = candles[self.ticker_column].astype(str)
        if "is_complete" in candles.columns:
            candles = candles.loc[candles["is_complete"].fillna(False)]

        results: list[tuple[pd.DataFrame, int, float]] = []
        grouped = candles.sort_values([self.ticker_column, self.time_column]).groupby(
            self.ticker_column, sort=False
        )
        for asset_name in asset_names.astype(str):
            if asset_name not in grouped.groups:
                results.append((pd.DataFrame(), 0, np.nan))
                continue
            asset_candles = grouped.get_group(asset_name).reset_index(drop=True)
            feature_frame = self._feature_frame(asset_candles)
            if feature_frame is None:
                results.append((pd.DataFrame(), len(asset_candles), np.nan))
                continue
            used = min(len(feature_frame), self.lookback_bars)
            latest_return = float(feature_frame["return"].iloc[-1])
            results.append((feature_frame.tail(self.lookback_bars), used, latest_return))
        return results

    def _feature_frame(self, candles: pd.DataFrame) -> pd.DataFrame | None:
        close = pd.to_numeric(candles[self.close_column], errors="coerce")
        high = pd.to_numeric(candles[self.high_column], errors="coerce")
        low = pd.to_numeric(candles[self.low_column], errors="coerce")
        volume = pd.to_numeric(candles[self.volume_column], errors="coerce")

        features: dict[str, pd.Series] = {
            "return": close.pct_change(fill_method=None),
            "intraday_range": (high - low) / close,
            "volume_change": volume.pct_change(fill_method=None),
        }
        frame = pd.DataFrame(
            {feature: features[feature] for feature in self.feature_columns}
        )
        frame = frame.replace([np.inf, -np.inf], np.nan).dropna(how="any")
        if frame.empty:
            return None
        return frame

    def _validate_parameters(self) -> None:
        if not isinstance(self.lookback_bars, int) or self.lookback_bars < 5:
            raise ValueError("lookback_bars must be an integer of at least 5")
        if self.direction not in VALID_DIRECTIONS:
            raise ValueError(
                f"direction must be one of {sorted(VALID_DIRECTIONS)}, "
                f"got {self.direction!r}"
            )
        if not self.feature_columns or not set(self.feature_columns).issubset(
            self.VALID_FEATURES
        ):
            raise ValueError(
                f"feature_columns must be a non-empty subset of {sorted(self.VALID_FEATURES)}"
            )