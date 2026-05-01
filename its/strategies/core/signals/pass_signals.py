from __future__ import annotations

from typing import Any

import numpy as np
import sklearn.utils.validation as skv

from its.strategies.core.types.signals_types import Siglans


class KeepAllSignal(Siglans):
    """Pass-through selector used when no additional signal filter is needed."""

    def fit(self, X: Any, y: Any = None) -> "KeepAllSignal":
        X = skv.validate_data(self, X, ensure_all_finite="allow-nan")
        self.to_keep_ = np.ones(X.shape[1], dtype=bool)
        return self
