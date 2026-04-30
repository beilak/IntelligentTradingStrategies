import dataclasses

import pandas as pd

from sklearn.pipeline import Pipeline


@dataclasses.dataclass(slots=True, frozen=True, kw_only=True)
class Strategy:
    name: str
    description: str
    pipeline: Pipeline


class StrategyBuilder:
    def __init__(
        self,
        _asset_universe_prices,
        _assets_info: pd.DataFrame | None = None,
        _runtime_context: dict | None = None,
    ) -> None:
        self._asset_universe_prices = _asset_universe_prices
        self._assets_info = _assets_info
        self._runtime_context = _runtime_context or {}

    def build(self) -> Strategy: ...
