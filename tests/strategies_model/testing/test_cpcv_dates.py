from __future__ import annotations

from typing import ClassVar

import numpy as np
import pandas as pd
from skfolio.model_selection import CombinatorialPurgedCV
from skfolio.portfolio import Portfolio
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.pipeline import Pipeline

from its.strategies.models import ModelEquityLiquidityMomentumEqualWeightBuilder
from its.strategies.testing.cpcv.core import causal_cpcv_predict


class ContextAuditTransformer(TransformerMixin, BaseEstimator):
    context_ends: ClassVar[list[pd.Timestamp]] = []
    train_ends: ClassVar[list[pd.Timestamp]] = []

    def __init__(self, asset_universe_prices: pd.DataFrame) -> None:
        self.asset_universe_prices = asset_universe_prices

    def fit(self, X: pd.DataFrame, y=None):
        self.context_ends.append(pd.Timestamp(self.asset_universe_prices["time"].max()))
        self.train_ends.append(pd.Timestamp(X.index.max()))
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        return X


class TestDateAuditEstimator(BaseEstimator):
    test_starts: ClassVar[list[pd.Timestamp]] = []

    def fit(self, X: pd.DataFrame, y=None):
        self.weights_ = np.full(X.shape[1], 1.0 / X.shape[1])
        return self

    def predict(self, X: pd.DataFrame) -> Portfolio:
        self.test_starts.append(pd.Timestamp(X.index.min()))
        return Portfolio(X=X, weights=self.weights_)


def test_causal_cpcv_never_fits_on_or_after_test_start() -> None:
    ContextAuditTransformer.context_ends.clear()
    ContextAuditTransformer.train_ends.clear()
    TestDateAuditEstimator.test_starts.clear()
    dates = pd.bdate_range("2024-01-02", periods=300)
    returns = pd.DataFrame(
        {
            "AAA": np.linspace(-0.01, 0.01, len(dates)),
            "BBB": np.linspace(0.01, -0.01, len(dates)),
        },
        index=dates,
    )
    x_train = returns.iloc[:100]
    x_test = returns.iloc[100:]
    future_dates = pd.bdate_range(dates.min(), "2026-12-31")
    context = pd.DataFrame(
        {
            "time": future_dates,
            "ticker": "AAA",
            "close": np.arange(len(future_dates), dtype=float) + 100.0,
        }
    )
    pipeline = Pipeline(
        [
            ("context_audit", ContextAuditTransformer(context)),
            ("allocation", TestDateAuditEstimator()),
        ]
    )
    cv = CombinatorialPurgedCV(n_folds=5, n_test_folds=2)

    population = causal_cpcv_predict(pipeline, x_train, x_test, cv)

    assert len(population) == 4
    for path in population:
        assert path.returns_df.index.equals(x_test.index)
    assert ContextAuditTransformer.context_ends
    assert ContextAuditTransformer.context_ends == ContextAuditTransformer.train_ends
    assert len(ContextAuditTransformer.train_ends) == len(
        TestDateAuditEstimator.test_starts
    )
    for train_end, test_start in zip(
        ContextAuditTransformer.train_ends,
        TestDateAuditEstimator.test_starts,
        strict=True,
    ):
        assert train_end < test_start


def test_causal_cpcv_empty_liquidity_selection_becomes_cash() -> None:
    dates = pd.bdate_range("2022-01-03", periods=500)
    returns = pd.DataFrame(
        {
            "AAA": np.linspace(-0.01, 0.01, len(dates)),
            "BBB": np.linspace(0.01, -0.01, len(dates)),
        },
        index=dates,
    )
    context = pd.DataFrame(
        [
            {
                "time": date,
                "ticker": ticker,
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.0,
                "volume": 0.0,
                "is_complete": True,
            }
            for date in dates
            for ticker in returns.columns
        ]
    )
    pipeline = ModelEquityLiquidityMomentumEqualWeightBuilder(context).build().pipeline
    cv = CombinatorialPurgedCV(n_folds=5, n_test_folds=2)

    population = causal_cpcv_predict(
        pipeline,
        returns.iloc[:200],
        returns.iloc[200:],
        cv,
    )
    parallel_population = causal_cpcv_predict(
        pipeline,
        returns.iloc[:200],
        returns.iloc[200:],
        cv,
        n_jobs=4,
    )

    assert len(population) == len(parallel_population)
    for sequential_path, parallel_path in zip(
        population, parallel_population, strict=True
    ):
        assert np.allclose(sequential_path.returns, 0.0)
        assert np.array_equal(sequential_path.returns, parallel_path.returns)
