from its.ga.types import GeneDefinition
from its.strategies.core.signals import KeepAllSignal

GENES = [
    GeneDefinition(
        id="pass_signal",
        title="Pass-signal",
        description="Do not apply an additional signal filter after pre-selection.",
        group="signal",
        component=KeepAllSignal,
    ),
]
