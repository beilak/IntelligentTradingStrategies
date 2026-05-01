from __future__ import annotations

from typing import Any

import numpy as np
import sklearn.base as skb
import sklearn.feature_selection as skf
import sklearn.utils.validation as skv

from its.strategies.core.types.dataframe_selector_mixin import DataFrameSelectorMixin


class KeepAllSelector(DataFrameSelectorMixin, skb.BaseEstimator, skf.SelectorMixin):
    """Pass-through selector used when no additional signal filter is needed."""

    to_keep_: np.ndarray

    def fit(self, X: Any, y: Any = None) -> "KeepAllSelector":
        X = skv.validate_data(self, X, ensure_all_finite="allow-nan")
        self.to_keep_ = np.ones(X.shape[1], dtype=bool)
        return self

    def _get_support_mask(self) -> np.ndarray:
        skv.check_is_fitted(self)
        return self.to_keep_

    def __sklearn_tags__(self):
        tags = super().__sklearn_tags__()
        tags.input_tags.allow_nan = True
        return tags
