from __future__ import annotations

from typing import Any

import numpy as np
import sklearn.utils.validation as skv

from its.strategies.core.types.signals_types import Siglans


class TwoCandlePositiveTrendSignal(Siglans):
    """Select assets where the last `n_candles` have positive returns >= `min_pct_increase`."""

    to_keep_: np.ndarray

    def __init__(self, n_candles: int = 2, min_pct_increase: float = 0.0):
        self.n_candles = n_candles
        self.min_pct_increase = min_pct_increase

    def fit(self, X: Any, y: Any = None) -> "TwoCandlePositiveTrendSignal":
        X = skv.validate_data(self, X, ensure_all_finite="allow-nan")
        n_samples, n_features = X.shape
        if n_samples < self.n_candles + 1:
            raise ValueError(
                f"X must have at least {self.n_candles + 1} samples, got {n_samples}"
            )

        self.to_keep_ = np.zeros(n_features, dtype=bool)
        for j in range(n_features):
            prices = X[:, j]
            returns = (prices[1:] - prices[:-1]) / prices[:-1] * 100
            last_returns = returns[-self.n_candles :]
            if np.all(last_returns >= self.min_pct_increase):
                self.to_keep_[j] = True
        return self
