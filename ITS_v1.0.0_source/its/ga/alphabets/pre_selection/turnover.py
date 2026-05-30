from its.ga.types import GeneDefinition
from its.strategies.core.selectors import IntradayTurnoverSelector, SafeEmptySelector

GENES = [
    GeneDefinition(
        id="turnover_1m_10",
        title="Turnover 1M / 10 bars",
        description="Select assets with at least 1M rubles turnover over the last 10 bars.",
        group="pre_selection",
        component=IntradayTurnoverSelector,
        component_kwargs={
            "lookback_bars": 10,
            "min_turnover": 1_000_000,
            "allow_empty_selection": False,
        },
        asset_universe_arg="asset_universe_prices",
        wrapper=SafeEmptySelector,
    ),
    GeneDefinition(
        id="turnover_25m_20",
        title="Turnover 25M / 20 bars",
        description="Select more liquid assets using a 25M ruble turnover threshold.",
        group="pre_selection",
        component=IntradayTurnoverSelector,
        component_kwargs={
            "lookback_bars": 20,
            "min_turnover": 25_000_000,
            "allow_empty_selection": False,
        },
        asset_universe_arg="asset_universe_prices",
        wrapper=SafeEmptySelector,
    ),
]
