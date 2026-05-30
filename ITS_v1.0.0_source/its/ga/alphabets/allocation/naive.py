from its.ga.types import GeneDefinition
from its.strategies.core.optimization import (
    CVaR,
    CVaRHighRisk,
    EqualWeighted,
    HierarchicalRiskParity,
    InverseVolatility,
)

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
    GeneDefinition(
        id="HierarchicalRiskParity",
        title="HRP",
        description="Allocate weight hierarchical risk parity",
        group="allocation",
        component=HierarchicalRiskParity,
        component_kwargs={"raise_on_failure": False},
    ),
    GeneDefinition(
        id="CVaR",
        title="CVaR",
        description="Allocate weight CVaR",
        group="allocation",
        component=CVaR,
        component_kwargs={"beta": 0.95},
    ),
    GeneDefinition(
        id="CVaRHighRisk",
        title="CVaRHighRisk",
        description="Allocate weight CVaRHighRisk",
        group="allocation",
        component=CVaRHighRisk,
        component_kwargs={"beta": 0.95},
    ),
]
