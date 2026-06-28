from typing import Any

import numpy as np
import sklearn.utils.validation as skv

from its.strategies.core.types.selectors_types import Selectros


class ExampleSelector(Selectros):
    def __init__(self, threshold: float = 0.0):
        self.threshold = threshold

    def fit(self, X: Any, y: Any = None) -> "ExampleSelector":
        values = skv.validate_data(self, X, ensure_all_finite="allow-nan")
        if not np.isfinite(self.threshold):
            raise ValueError("threshold must be finite")
        # TODO: one boolean per input column.
        self.to_keep_ = np.zeros(values.shape[1], dtype=bool)
        return self

