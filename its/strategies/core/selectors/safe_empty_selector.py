import numpy as np
import sklearn.base as skb
import sklearn.feature_selection as skf

from its.strategies.core.dataframe_selector_mixin import DataFrameSelectorMixin


class SafeEmptySelector(DataFrameSelectorMixin, skb.BaseEstimator, skf.SelectorMixin):
    """
    Обёртка для селекторов (например, TrendSelector), чтобы pipeline
    не ломался, если нет выбранных признаков.

    Возвращает нулевую матрицу того же размера, если селектор ничего не выбрал.
    """

    def __init__(self, selector):
        self.selector = selector
        self.empty_selection_ = False

    def fit(self, X, y=None):
        # вызываем fit у настоящего селектора
        self.selector.fit(X, y)
        # проверяем, пуст ли выбор
        self.empty_selection_ = (
            getattr(self.selector, "empty_selection_", False)
            or not self.selector._get_support_mask().any()
        )
        return self

    def transform(self, X):
        mask = self.selector._get_support_mask()

        if hasattr(X, "iloc"):
            if not mask.any():
                # если ничего не выбрано, возвращаем нулевую таблицу с теми же
                # индексом и названиями тикеров, чтобы downstream-аллокатор
                # не терял реальные имена активов
                return self.zero_like_input(X)
            return X.loc[:, mask]

        X_t = self.selector.transform(X)
        if X_t.shape[1] == 0:
            return self.zero_like_input(X)
        return X_t

    def _get_support_mask(self):
        return self.selector._get_support_mask()
