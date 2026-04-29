from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import sklearn.utils.validation as skv


class DataFrameSelectorMixin:
    """Preserve DataFrame index/columns when selector-like steps transform X."""

    def transform(self, X: Any) -> Any:
        skv.check_is_fitted(self)
        mask = self._get_support_mask()
        if hasattr(X, "iloc"):
            skv.validate_data(self, X, ensure_all_finite="allow-nan", reset=False)
            return X.loc[:, mask]
        X = skv.validate_data(self, X, ensure_all_finite="allow-nan", reset=False)
        return X[:, mask]

    @staticmethod
    def zero_like_input(X: Any) -> Any:
        if hasattr(X, "iloc"):
            return pd.DataFrame(
                np.zeros_like(X),
                index=X.index,
                columns=X.columns,
            )
        return np.zeros_like(X)
