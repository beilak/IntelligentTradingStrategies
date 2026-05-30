from its.ga.types import GeneDefinition
from its.strategies.core.selectors import SafeEmptySelector, SectorSelector

GENES = [
    GeneDefinition(
        id="sector_it_telecom",
        title="Sector: IT + Telecom",
        description="Select assets from IT and telecom sectors.",
        group="pre_selection",
        component=SectorSelector,
        component_kwargs={
            "sectors": ["it", "telecom"],
        },
        wrapper=SafeEmptySelector,
        runtime_args={"assets_info": "assets_info"},
    ),
    GeneDefinition(
        id="sector_energy_telecom",
        title="Sector: energy_telecom",
        description="Select assets from energy and telecom",
        group="pre_selection",
        component=SectorSelector,
        component_kwargs={
            "sectors": ["energy", "telecom"],
        },
        wrapper=SafeEmptySelector,
        runtime_args={"assets_info": "assets_info"},
    ),
]
