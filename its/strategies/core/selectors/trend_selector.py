import numpy as np
import numpy.typing as npt
import pandas as pd
import sklearn.base as skb
import sklearn.feature_selection as skf
import sklearn.linear_model as skl
import sklearn.utils.validation as skv
from sklearn.utils.validation import validate_data

from its.strategies.core.types.dataframe_selector_mixin import DataFrameSelectorMixin


class TrendSelector(DataFrameSelectorMixin, skf.SelectorMixin, skb.BaseEstimator):
    """
    Pre-selection по тренду: оставляем бумаги с положительным трендом
    за последние N дат.

    Parameters
    ----------
    window : int
        Количество последних дат для расчета линейной регрессии.
    """

    to_keep_: np.ndarray

    def __init__(self, window: int = 20):
        self.window = window

    def fit(self, X: npt.ArrayLike, y=None):
        # X = self._validate_data(X, reset=True)
        X = validate_data(self, X, reset=True)
        n_obs, n_assets = X.shape
        self.to_keep_ = np.zeros(n_assets, dtype=bool)

        for i in range(n_assets):
            y_asset = X[-self.window :, i]
            x = np.arange(len(y_asset)).reshape(-1, 1)
            model = skl.LinearRegression().fit(x, y_asset)
            if model.coef_[0] > 0:  # положительный тренд
                self.to_keep_[i] = True

        return self

    def _get_support_mask(self):
        skv.check_is_fitted(self)
        return self.to_keep_


class TrendThresholdSelector(
    DataFrameSelectorMixin, skf.SelectorMixin, skb.BaseEstimator
):
    """
    Pre-selection по тренду с порогом наклона.

    Parameters
    ----------
    window : int
        Количество последних дат для расчета линейной регрессии.
    slope_threshold : float
        Минимальный наклон, чтобы оставлять бумагу.
        Положительный — рост, отрицательный — падение.
    """

    to_keep_: np.ndarray

    def __init__(self, window: int = 20, slope_threshold: float = 0.0):
        self.window = window
        self.slope_threshold = slope_threshold

    def fit(self, X: npt.ArrayLike, y=None):
        # X = self._validate_data(X, reset=True)
        X = validate_data(self, X, reset=True)
        n_obs, n_assets = X.shape
        self.to_keep_ = np.zeros(n_assets, dtype=bool)

        for i in range(n_assets):
            y_asset = X[-self.window :, i]
            x = np.arange(len(y_asset)).reshape(-1, 1)
            model = skl.LinearRegression().fit(x, y_asset)
            if model.coef_[0] >= self.slope_threshold:
                self.to_keep_[i] = True

        return self

    def _get_support_mask(self):
        skv.check_is_fitted(self)
        return self.to_keep_
