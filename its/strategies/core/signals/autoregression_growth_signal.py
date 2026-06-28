from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import numpy as np
import pandas as pd
import sklearn.utils.validation as skv
from statsmodels.tsa.ar_model import AutoReg

from its.strategies.core.types.signals_types import Siglans


class AutoRegressionGrowthSignal(Siglans):
    """Select assets whose autoregression forecast exceeds required growth."""

    to_keep_: np.ndarray

    def __init__(
        self,
        lookback_bars: int = 60,
        lags: int = 5,
        forecast_bars: int = 1,
        min_growth_pct: float = 0.01,
        n_jobs: int | None = None,
    ):
        self.lookback_bars = lookback_bars
        self.lags = lags
        self.forecast_bars = forecast_bars
        self.min_growth_pct = min_growth_pct
        self.n_jobs = n_jobs

    def fit(self, X: Any, y: Any = None) -> "AutoRegressionGrowthSignal":
        self._validate_parameters()
        X_validated = skv.validate_data(self, X, ensure_all_finite="allow-nan")
        asset_names = (
            self.feature_names_in_.astype(str)
            if hasattr(self, "feature_names_in_")
            else np.asarray([f"asset_{index}" for index in range(X_validated.shape[1])])
        )

        predicted_growth = np.full(X_validated.shape[1], np.nan)
        observations_used = np.zeros(X_validated.shape[1], dtype=int)
        worker_count = self._worker_count(X_validated.shape[1])
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            forecasts = executor.map(
                self._forecast_growth,
                (X_validated[:, index] for index in range(X_validated.shape[1])),
            )
            for index, (growth, observations) in enumerate(forecasts):
                predicted_growth[index] = growth
                observations_used[index] = observations

        self.to_keep_ = np.isfinite(predicted_growth) & (
            predicted_growth >= self.min_growth_pct
        )
        self.predicted_growth_ = pd.Series(predicted_growth, index=asset_names)
        self.observations_used_ = pd.Series(observations_used, index=asset_names)
        return self

    def _forecast_growth(self, values: np.ndarray) -> tuple[float, int]:
        returns = values[np.isfinite(values)][-self.lookback_bars :]
        observations = len(returns)
        if observations < self.lookback_bars:
            return np.nan, observations
        try:
            model = AutoReg(
                returns,
                lags=self.lags,
                trend="ct",
                old_names=False,
            ).fit()
            forecast = np.asarray(
                model.predict(
                    start=len(returns),
                    end=len(returns) + self.forecast_bars - 1,
                    dynamic=False,
                ),
                dtype=float,
            )
        except (ValueError, np.linalg.LinAlgError):
            return np.nan, observations
        if len(forecast) != self.forecast_bars or not np.isfinite(forecast).all():
            return np.nan, observations
        return float(np.prod(1.0 + forecast) - 1.0), observations

    def _worker_count(self, asset_count: int) -> int:
        configured = self.n_jobs
        if configured is None:
            configured = int(os.getenv("ITS_AUTOREG_MAX_WORKERS", "4"))
        return max(1, min(configured, asset_count))

    def _validate_parameters(self) -> None:
        if self.lookback_bars <= 2:
            raise ValueError("lookback_bars must be greater than 2")
        if self.lags <= 0 or self.lags >= self.lookback_bars - 1:
            raise ValueError("lags must be positive and leave data for estimation")
        if self.forecast_bars <= 0:
            raise ValueError("forecast_bars must be positive")
        if not np.isfinite(self.min_growth_pct):
            raise ValueError("min_growth_pct must be finite")
        if self.n_jobs is not None and self.n_jobs <= 0:
            raise ValueError("n_jobs must be positive")
