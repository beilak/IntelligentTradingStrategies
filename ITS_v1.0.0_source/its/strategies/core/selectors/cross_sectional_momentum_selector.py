import numpy as np
import pandas as pd
from sklearn.utils.validation import check_is_fitted
from sklearn.utils.validation import validate_data

from its.strategies.core.types.selectors_types import Selectros


class CrossSectionalMomentumSelector(Selectros):
    """
    Селектор на основе cross-sectional momentum.

    Parameters
    ----------
    lookback : int
        Период для расчета доходности (в днях)
    quantile : float, default=0.3
        Доля активов с наивысшей доходностью, которые нужно оставить.
    min_periods : int, default=20
        Минимальное количество наблюдений для расчета доходности.
    """

    def __init__(
        self, lookback: int = 63, quantile: float = 0.3, min_periods: int = 20
    ):
        self.lookback = lookback
        self.quantile = quantile
        self.min_periods = min_periods

    def fit(self, X, y=None):
        if self.lookback <= 0:
            raise ValueError("lookback must be positive")
        if not 0 < self.quantile <= 1:
            raise ValueError("quantile must be in the interval (0, 1]")
        if self.min_periods <= 0:
            raise ValueError("min_periods must be positive")

        original_columns = X.columns if isinstance(X, pd.DataFrame) else None
        X_validated = validate_data(
            self,
            X,
            ensure_all_finite="allow-nan",
            reset=True,
        )
        if isinstance(X, pd.DataFrame):
            prices = X
        else:
            prices = pd.DataFrame(X_validated)

        n_assets = prices.shape[1]
        self.asset_names_ = (
            original_columns.to_numpy()
            if original_columns is not None
            else np.arange(n_assets).astype(str)
        )
        self.fallback_reason_ = None

        # ЗАЩИТА: Проверяем, достаточно ли данных для расчета
        if len(prices) < self.min_periods:
            return self._keep_all(
                n_assets,
                f"not enough data ({len(prices)} rows) for momentum calculation",
            )

        # Рассчитываем доходность за период lookback
        returns = prices.pct_change(periods=self.lookback, fill_method=None)

        # ЗАЩИТА: Проверяем, есть ли данные после pct_change
        if returns.empty:
            return self._keep_all(n_assets, "returns DataFrame is empty")

        # Берем последнюю доходность для каждого актива
        try:
            latest_returns = returns.iloc[-1].fillna(-np.inf)
        except IndexError:
            # Если не можем взять последнюю строку, возвращаем все активы
            return self._keep_all(n_assets, "cannot access last row of returns")

        # Сохраняем скоры
        self.momentum_scores_ = latest_returns.to_numpy()

        # Проверяем, есть ли конечные значения для расчета квантиля
        finite_returns = latest_returns[latest_returns > -np.inf]

        if len(finite_returns) == 0:
            # Если нет валидных доходностей, оставляем все активы
            return self._keep_all(n_assets, "no valid returns found")

        # Определяем порог для отбора
        if len(finite_returns) == 1:
            # Если только один актив с данными, сравниваем с нулем
            threshold = 0
        else:
            threshold = np.quantile(finite_returns, 1 - self.quantile)

        # Формируем маску для отбора
        mask = latest_returns >= threshold

        # Проверяем минимальное количество наблюдений
        valid_counts = prices.count()
        enough_data = valid_counts >= self.min_periods
        self.to_keep_ = (mask & enough_data).to_numpy(dtype=bool)

        return self

    def _keep_all(self, n_assets: int, reason: str):
        self.fallback_reason_ = reason
        self.to_keep_ = np.ones(n_assets, dtype=bool)
        self.momentum_scores_ = np.zeros(n_assets)
        return self

    def get_momentum_scores(self):
        check_is_fitted(self)
        return pd.Series(
            self.momentum_scores_,
            index=self.asset_names_,
            name="momentum_scores",
        )
