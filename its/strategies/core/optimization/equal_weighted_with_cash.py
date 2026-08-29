from __future__ import annotations

from typing import Any

import numpy as np
from skfolio.optimization import EqualWeighted


class EqualWeightedWithCash(EqualWeighted):
    """Allocate equally while reserving part of the portfolio as cash."""

    def __init__(
        self,
        allocation_pct: float = 0.70,
        portfolio_params: dict | None = None,
        fallback: Any = None,
        previous_weights: Any = None,
        raise_on_failure: bool = True,
    ) -> None:
        super().__init__(
            portfolio_params=portfolio_params,
            fallback=fallback,
            previous_weights=previous_weights,
            raise_on_failure=raise_on_failure,
        )
        self.allocation_pct = allocation_pct

    def fit(self, X: Any, y: Any = None) -> EqualWeightedWithCash:
        """Fit equal weights and scale them to the requested allocation."""
        if not np.isfinite(self.allocation_pct) or not 0 <= self.allocation_pct <= 1:
            raise ValueError("allocation_pct must be in the interval [0, 1]")

        super().fit(X, y)
        self.weights_ = self.weights_ * float(self.allocation_pct)
        self.cash_weight_ = 1.0 - float(self.allocation_pct)
        return self
