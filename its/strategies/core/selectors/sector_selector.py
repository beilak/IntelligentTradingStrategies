import numpy as np
import pandas as pd
import sklearn.base as skb
import sklearn.feature_selection as skf

from its.strategies.core.dataframe_selector_mixin import DataFrameSelectorMixin


class SectorSelector(DataFrameSelectorMixin, skf.SelectorMixin, skb.BaseEstimator):
    """
    Селектор бумаг по сектору.

    Parameters
    ----------
    assets_info : pd.DataFrame
        Таблица с информацией о бумагах, должна содержать колонку 'sector'.
        Индекс должен совпадать с тикерами в X (колонки X).

    sectors : list[str]
        Список секторов, которые нужно оставить.
    """

    to_keep_: np.ndarray

    def __init__(self, assets_info: pd.DataFrame, sectors: list[str]):
        self.assets_info = assets_info
        self.sectors = sectors

    def fit(self, X, y=None):
        # проверяем, что все колонки X есть в assets_info

        tickers = (
            X.columns
            if isinstance(X, pd.DataFrame)
            else [f"asset_{i}" for i in range(X.shape[1])]
        )
        sectors_in_data = self.assets_info.set_index("ticker").reindex(tickers)[
            "sector"
        ]

        # создаём булев маск, True = оставляем
        self.to_keep_ = sectors_in_data.isin(self.sectors).fillna(False).values

        return self

    def _get_support_mask(self):
        skb.check_is_fitted(self)
        return self.to_keep_
