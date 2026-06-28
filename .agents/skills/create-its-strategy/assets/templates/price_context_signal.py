from typing import Any

import numpy as np
import pandas as pd
import sklearn.utils.validation as skv

from its.strategies.core.types.signals_types import Siglans


class ExamplePriceContextSignal(Siglans):
    def __init__(
        self,
        lookback_bars: int = 20,
        threshold: float = 0.0,
        asset_universe_prices: pd.DataFrame | None = None,
    ):
        self.lookback_bars = lookback_bars
        self.threshold = threshold
        self.asset_universe_prices = asset_universe_prices

    def fit(self, X: Any, y: Any = None) -> "ExamplePriceContextSignal":
        values = skv.validate_data(self, X, ensure_all_finite="allow-nan")
        if self.asset_universe_prices is None:
            raise ValueError("asset_universe_prices is required")
        required = {"time", "ticker", "close"}  # TODO: add OHLCV requirements.
        missing = required.difference(self.asset_universe_prices.columns)
        if missing:
            raise ValueError(f"asset_universe_prices missing: {sorted(missing)}")
        names = getattr(self, "feature_names_in_", np.arange(values.shape[1]))
        scores = np.full(values.shape[1], np.nan)
        candles = self.asset_universe_prices.copy()
        candles["time"] = pd.to_datetime(candles["time"], errors="coerce")
        candles["close"] = pd.to_numeric(candles["close"], errors="coerce")
        if "is_complete" in candles:
            candles = candles.loc[candles["is_complete"].fillna(False)]
        for index, ticker in enumerate(names.astype(str)):
            recent = candles.loc[candles["ticker"].astype(str) == ticker].tail(
                self.lookback_bars
            )
            if len(recent) == self.lookback_bars:
                scores[index] = float(recent["close"].iloc[-1])  # TODO: formula.
        self.scores_ = pd.Series(scores, index=names)
        self.to_keep_ = np.isfinite(scores) & (scores >= self.threshold)
        return self

