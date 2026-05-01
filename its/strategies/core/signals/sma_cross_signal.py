from __future__ import annotations

from typing import Any

import numpy as np
import sklearn.base as skb
import sklearn.feature_selection as skf
import sklearn.utils.validation as skv

from its.strategies.core.types.dataframe_selector_mixin import DataFrameSelectorMixin
from its.strategies.core.types.signals_types import Siglans


class SMACrossSignal(Siglans):
    """Select assets where the short-term SMA crosses above the long-term SMA (golden cross)."""

    to_keep_: np.ndarray

    def __init__(self, short_window: int = 20, long_window: int = 50):
        if short_window >= long_window:
            raise ValueError("short_window must be less than long_window")
        self.short_window = short_window
        self.long_window = long_window

    def fit(self, X: Any, y: Any = None) -> "SMACrossSignal":
        X = skv.validate_data(self, X, ensure_all_finite="allow-nan")
        n_samples, n_features = X.shape
        if n_samples < self.long_window + 1:
            raise ValueError(
                f"X must have at least {self.long_window + 1} samples, got {n_samples}"
            )

        self.to_keep_ = np.zeros(n_features, dtype=bool)
        for j in range(n_features):
            prices = X[:, j]
            t_last = n_samples - 1
            t_prev = t_last - 1

            if t_prev < self.long_window - 1:
                continue

            short_last = np.mean(prices[t_last - self.short_window + 1 : t_last + 1])
            short_prev = np.mean(prices[t_prev - self.short_window + 1 : t_prev + 1])
            long_last = np.mean(prices[t_last - self.long_window + 1 : t_last + 1])
            long_prev = np.mean(prices[t_prev - self.long_window + 1 : t_prev + 1])

            if (short_prev <= long_prev) and (short_last > long_last):
                self.to_keep_[j] = True
        return self
