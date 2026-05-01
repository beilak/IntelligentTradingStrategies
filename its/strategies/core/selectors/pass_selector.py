from __future__ import annotations

from typing import Any

import numpy as np
import sklearn.utils.validation as skv

from its.strategies.core.types.dataframe_selector_mixin import DataFrameSelectorMixin
from its.strategies.core.types.selectors_types import Selectros


class KeepAllSelector(Selectros):
    """Pass-through selector used when no additional signal filter is needed."""

    to_keep_: np.ndarray

    def fit(self, X: Any, y: Any = None) -> "KeepAllSelector":
        X = skv.validate_data(self, X, ensure_all_finite="allow-nan")
        self.to_keep_ = np.ones(X.shape[1], dtype=bool)
        return self
