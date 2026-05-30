from its.ga.types import GeneDefinition
from its.strategies.core.selectors import CrossSectionalMomentumSelector, SafeEmptySelector

GENES = [
    GeneDefinition(
        id="CrossSectionalMomentumSelector",
        title="CrossSectionalMomentumSelector",
        description="Cross-sectional momentum based Select",
        group="pre_selection",
        component=CrossSectionalMomentumSelector,
        wrapper=SafeEmptySelector,
    )
]
