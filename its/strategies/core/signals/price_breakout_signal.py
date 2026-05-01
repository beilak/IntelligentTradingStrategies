from __future__ import annotations

from typing import Any

import numpy as np
import sklearn.base as skb
import sklearn.feature_selection as skf
import sklearn.utils.validation as skv

from its.strategies.core.types.dataframe_selector_mixin import DataFrameSelectorMixin


class PriceBreakoutSignal(DataFrameSelectorMixin, skb.BaseEstimator, skf.SelectorMixin):
    """Select assets where current price breaks above the highest price of the last `lookback_window` candles."""

    to_keep_: np.ndarray

    def __init__(self, lookback_window: int = 20):
        self.lookback_window = lookback_window

    def fit(self, X: Any, y: Any = None) -> "PriceBreakoutSignal":
        X = skv.validate_data(self, X, ensure_all_finite="allow-nan")
        n_samples, n_features = X.shape
        if n_samples < self.lookback_window + 1:
            raise ValueError(
                f"X must have at least {self.lookback_window + 1} samples, got {n_samples}"
            )

        self.to_keep_ = np.zeros(n_features, dtype=bool)
        for j in range(n_features):
            prices = X[:, j]
            current = prices[-1]
            lookback_max = np.max(prices[-self.lookback_window - 1 : -1])
            if current > lookback_max:
                self.to_keep_[j] = True
        return self

    def _get_support_mask(self) -> np.ndarray:
        skv.check_is_fitted(self)
        return self.to_keep_

    def __sklearn_tags__(self):
        tags = super().__sklearn_tags__()
        tags.input_tags.allow_nan = True
        return tags
