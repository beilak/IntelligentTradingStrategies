import dataclasses

from sklearn.pipeline import Pipeline


@dataclasses.dataclass(slots=True, frozen=True, kw_only=True)
class Strategy:
    name: str
    description: str
    pipeline: Pipeline


class StrategyBuilder:
    def __init__(self, _asset_universe_prices) -> None:
        self._asset_universe_prices = _asset_universe_prices

    def build(self) -> Strategy: ...
