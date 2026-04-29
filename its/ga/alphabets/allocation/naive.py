from its.ga.types import GeneDefinition
from its.strategies.core.optimization import EqualWeighted, InverseVolatility

GENES = [
    GeneDefinition(
        id="equal_weighted",
        title="Equal Weighted",
        description="Allocate the selected universe with equal weights.",
        group="allocation",
        component=EqualWeighted,
    ),
    GeneDefinition(
        id="inverse_volatility",
        title="Inverse Volatility",
        description="Allocate more weight to lower-volatility assets.",
        group="allocation",
        component=InverseVolatility,
        component_kwargs={"raise_on_failure": False},
    ),
]
