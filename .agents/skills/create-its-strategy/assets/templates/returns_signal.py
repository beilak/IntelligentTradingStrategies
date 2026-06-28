from typing import Any

import numpy as np
import pandas as pd
import sklearn.utils.validation as skv

from its.strategies.core.types.signals_types import Siglans


class ExampleReturnsSignal(Siglans):
    def __init__(self, lookback_bars: int = 20, threshold: float = 0.0):
        self.lookback_bars = lookback_bars
        self.threshold = threshold

    def fit(self, X: Any, y: Any = None) -> "ExampleReturnsSignal":
        values = skv.validate_data(self, X, ensure_all_finite="allow-nan")
        if self.lookback_bars <= 0:
            raise ValueError("lookback_bars must be positive")
        scores = np.full(values.shape[1], np.nan)
        for index in range(values.shape[1]):
            history = values[:, index]
            history = history[np.isfinite(history)][-self.lookback_bars :]
            if len(history) == self.lookback_bars:
                scores[index] = float(np.mean(history))  # TODO: replace formula.
        names = getattr(self, "feature_names_in_", np.arange(values.shape[1]))
        self.scores_ = pd.Series(scores, index=names)
        self.to_keep_ = np.isfinite(scores) & (scores >= self.threshold)
        return self

