import sklearn.base as skb
import sklearn.feature_selection as skf
import sklearn.utils.validation as skv
from skfolio.typing import BoolArray

from its.strategies.core.types.dataframe_selector_mixin import DataFrameSelectorMixin


class Siglans(DataFrameSelectorMixin, skf.SelectorMixin, skb.BaseEstimator):
    STEP_TYPE: str = "signals"

    to_keep_: BoolArray

    def _get_support_mask(self) -> BoolArray:
        skv.check_is_fitted(self)
        return self.to_keep_

    def __sklearn_tags__(self):
        tags = super().__sklearn_tags__()
        tags.input_tags.allow_nan = True
        return tags
