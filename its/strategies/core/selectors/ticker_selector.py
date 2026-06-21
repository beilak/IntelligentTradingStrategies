from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import sklearn.utils.validation as skv

from its.strategies.core.types.selectors_types import Selectros


class TickerSelector(Selectros):
    """Select assets whose ticker is present in an explicit allow-list."""

    to_keep_: np.ndarray

    def __init__(self, tickers: list[str], allow_empty_selection: bool = False):
        self.tickers = tickers
        self.allow_empty_selection = allow_empty_selection

    def fit(self, X: Any, y: Any = None) -> "TickerSelector":
        X_validated = skv.validate_data(self, X, ensure_all_finite="allow-nan")
        selected_tickers = {str(ticker) for ticker in self.tickers}
        tickers = (
            X.columns
            if isinstance(X, pd.DataFrame)
            else [f"asset_{i}" for i in range(X_validated.shape[1])]
        )
        tickers = [str(ticker) for ticker in tickers]

        self.to_keep_ = np.asarray(
            [ticker in selected_tickers for ticker in tickers],
            dtype=bool,
        )
        if not self.to_keep_.any() and not self.allow_empty_selection:
            requested = ", ".join(self.tickers)
            available = ", ".join(tickers[:10])
            if len(tickers) > 10:
                available = f"{available}, ..."
            raise ValueError(
                "Ticker selector selected no assets present in X. "
                f"Requested tickers: {requested}. Available tickers: {available}."
            )
        return self
