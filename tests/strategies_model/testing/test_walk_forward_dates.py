from __future__ import annotations

from typing import ClassVar

import numpy as np
import pandas as pd
from skfolio.model_selection import WalkForward
from skfolio.portfolio import Portfolio
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.pipeline import Pipeline

from its.strategies.models import ModelEquityLiquidityMomentumEqualWeightBuilder
from its.strategies.testing.walk_forward.core import (
    collect_walk_forward_splits,
    walk_forward_cross_val_predict,
)


class ContextAuditTransformer(TransformerMixin, BaseEstimator):
    fitted_context_ends: ClassVar[list[pd.Timestamp]] = []
    fitted_return_ends: ClassVar[list[pd.Timestamp]] = []

    def __init__(self, asset_universe_prices: pd.DataFrame) -> None:
        self.asset_universe_prices = asset_universe_prices

    def fit(self, X: pd.DataFrame, y=None):
        self.fitted_context_ends.append(
            pd.Timestamp(self.asset_universe_prices["time"].max())
        )
        self.fitted_return_ends.append(pd.Timestamp(X.index.max()))
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        return X


class EqualWeightEstimator(BaseEstimator):
    def fit(self, X: pd.DataFrame, y=None):
        self.weights_ = np.full(X.shape[1], 1.0 / X.shape[1])
        return self

    def predict(self, X: pd.DataFrame) -> Portfolio:
        return Portfolio(X=X, weights=self.weights_)


def test_walk_forward_windows_are_strictly_chronological() -> None:
    returns = pd.DataFrame(
        {"AAA": np.linspace(0.0, 0.01, 520)},
        index=pd.bdate_range("2024-01-02", periods=520),
    )
    walk_forward = WalkForward(
        test_size=1,
        train_size=pd.DateOffset(months=3),
        freq=pd.DateOffset(months=3),
    )

    splits = collect_walk_forward_splits(walk_forward, returns)

    assert splits
    for split in splits:
        assert split["train_dates"].max() < split["test_dates"].min()
        assert split["test_dates"].max() <= returns.index.max()


def test_walk_forward_limits_long_price_context_to_each_train_end() -> None:
    ContextAuditTransformer.fitted_context_ends.clear()
    ContextAuditTransformer.fitted_return_ends.clear()
    dates = pd.bdate_range("2024-01-02", periods=520)
    returns = pd.DataFrame(
        {
            "AAA": np.linspace(-0.01, 0.01, len(dates)),
            "BBB": np.linspace(0.01, -0.01, len(dates)),
        },
        index=dates,
    )
    future_dates = pd.bdate_range(dates.min(), "2026-12-31")
    full_context = pd.DataFrame(
        {
            "time": future_dates,
            "ticker": "AAA",
            "close": np.arange(len(future_dates), dtype=float) + 100.0,
        }
    )
    pipeline = Pipeline(
        [
            ("context_audit", ContextAuditTransformer(full_context)),
            ("allocation", EqualWeightEstimator()),
        ]
    )
    walk_forward = WalkForward(
        test_size=1,
        train_size=pd.DateOffset(months=3),
        freq=pd.DateOffset(months=3),
    )
    splits = collect_walk_forward_splits(walk_forward, returns)

    population = walk_forward_cross_val_predict(pipeline, returns, splits)

    assert len(population) == len(splits)
    expected_train_ends = [pd.Timestamp(split["train_dates"].max()) for split in splits]
    assert ContextAuditTransformer.fitted_return_ends == expected_train_ends
    assert ContextAuditTransformer.fitted_context_ends == expected_train_ends
    for context_end, split in zip(
        ContextAuditTransformer.fitted_context_ends,
        splits,
        strict=True,
    ):
        assert context_end < split["test_dates"].min()


def test_walk_forward_empty_liquidity_selection_becomes_cash_fold() -> None:
    dates = pd.bdate_range("2024-01-02", periods=520)
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
    walk_forward = WalkForward(
        test_size=1,
        train_size=pd.DateOffset(months=3),
        freq=pd.DateOffset(months=3),
    )
    splits = collect_walk_forward_splits(walk_forward, returns)

    population = walk_forward_cross_val_predict(pipeline, returns, splits)

    assert len(population) == len(splits)
    for portfolio in population:
        assert np.allclose(portfolio.weights, 0.0)
        assert np.allclose(portfolio.returns, 0.0)
