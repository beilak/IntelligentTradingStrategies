from its.ga.types import GeneDefinition
from its.strategies.core.selectors import DividendHistorySelector

GENES = [
    GeneDefinition(
        id="DividendHistorySelector",
        title="DividendHistorySelector",
        description="Select assets that have paid dividends in each of the last N years before the last train date.",
        group="pre_selection",
        component=DividendHistorySelector,
        component_kwargs={
            "years": 3,
        },
        runtime_args={"dividends_df": "dividends_info"},
    )
]
