from dataclasses import dataclass
from typing import Any

import numpy as np
import sklearn.base as skb
import sklearn.utils.validation as skv


@dataclass(frozen=True)
class ExamplePortfolio:
    weights_dict: dict[str, float]


class ExampleAllocator(skb.BaseEstimator):
    def __init__(self, lookback_bars: int = 60):
        self.lookback_bars = lookback_bars

    def fit(self, X: Any, y: Any = None) -> "ExampleAllocator":
        values = skv.validate_data(self, X)
        if self.lookback_bars <= 1:
            raise ValueError("lookback_bars must be greater than 1")
        recent = values[-self.lookback_bars :]
        # TODO: calculate finite non-negative weights or raise a specific error.
        weights = np.full(recent.shape[1], 1.0 / recent.shape[1])
        self.weights_ = weights
        self.asset_names_ = [
            str(name)
            for name in getattr(self, "feature_names_in_", range(recent.shape[1]))
        ]
        return self

    def predict(self, X: Any) -> ExamplePortfolio:
        skv.check_is_fitted(self, ["weights_", "asset_names_"])
        return ExamplePortfolio(
            weights_dict=dict(zip(self.asset_names_, self.weights_, strict=True))
        )
