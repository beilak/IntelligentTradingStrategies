from its.ga.types import GeneDefinition
from its.strategies.core.selectors import SectorSelector

GENES = [
    GeneDefinition(
        id="turnover_1m_10",
        title="Turnover 1M / 10 bars",
        description="Select assets with at least 1M rubles turnover over the last 10 bars.",
        group="pre_selection",
        component=SectorSelector,
        component_kwargs={
            "assets_info": ...,
            "sectors": ["it", "telecom"],
        },
        asset_universe_arg="asset_universe_prices",
    ),
]
