from __future__ import annotations

import importlib
import inspect
import sys
from pathlib import Path
from typing import Any

from its.ga.types import AlphabetGroup, GeneDefinition

ALPHABET_GROUPS: tuple[AlphabetGroup, ...] = (
    "pre_selection",
    "signal",
    "allocation",
)
ALPHABET_PACKAGE = "its.ga.alphabets"


def load_alphabet_registry() -> dict[str, Any]:
    groups = []
    for group in ALPHABET_GROUPS:
        genes = load_gene_group(group)
        groups.append(
            {
                "id": group,
                "title": title_for_group(group),
                "count": len(genes),
                "items": [gene.to_dict() for gene in genes],
            }
        )
    search_space = 1
    for group in groups:
        search_space *= max(group["count"], 1)
    return {"groups": groups, "search_space": search_space}


def load_gene_group(group: AlphabetGroup) -> list[GeneDefinition]:
    package_name = f"{ALPHABET_PACKAGE}.{group}"
    package = import_fresh_module(package_name)
    package_path = Path(inspect.getfile(package)).parent
    genes: list[GeneDefinition] = []

    for path in sorted(package_path.glob("*.py")):
        if path.name.startswith("_"):
            continue
        module_name = f"{package_name}.{path.stem}"
        module = import_fresh_module(module_name)
        for raw_gene in getattr(module, "GENES", []):
            gene = normalize_gene(raw_gene)
            if gene.group != group:
                raise ValueError(
                    f"Gene {gene.id!r} is registered in {group!r}, "
                    f"but declares group {gene.group!r}."
                )
            genes.append(gene)
    return genes


def get_gene(group: AlphabetGroup, gene_id: str) -> GeneDefinition:
    for gene in load_gene_group(group):
        if gene.id == gene_id:
            return gene
    raise KeyError(f"Gene {gene_id!r} was not found in {group!r}.")


def build_component(
    gene: GeneDefinition,
    *,
    asset_universe_prices=None,
    runtime_context: dict[str, Any] | None = None,
):
    context = dict(runtime_context or {})
    if asset_universe_prices is not None:
        context.setdefault("asset_universe_prices", asset_universe_prices)

    component_path = gene.resolved_component_path()
    if component_path:
        component_cls = import_symbol(component_path)
        kwargs = dict(gene.component_kwargs)
        if gene.asset_universe_arg:
            kwargs[gene.asset_universe_arg] = context.get("asset_universe_prices")
        kwargs.update(resolve_runtime_kwargs(gene, context))
        component = component_cls(**kwargs)
        wrapper_path = gene.resolved_wrapper_path()
        if wrapper_path:
            wrapper_cls = import_symbol(wrapper_path)
            return wrapper_cls(component, **gene.wrapper_kwargs)
        return component

    if not gene.factory_path:
        raise ValueError(
            f"GA gene {gene.id!r} must define component/component_path or factory_path."
        )
    factory = import_symbol(gene.factory_path)
    kwargs = dict(gene.factory_kwargs)
    signature = inspect.signature(factory)
    if "asset_universe_prices" in signature.parameters:
        kwargs["asset_universe_prices"] = context.get("asset_universe_prices")
    kwargs.update(resolve_runtime_kwargs(gene, context))
    return factory(**kwargs)


def resolve_runtime_kwargs(
    gene: GeneDefinition,
    runtime_context: dict[str, Any],
) -> dict[str, Any]:
    missing = [
        context_key
        for context_key in gene.runtime_args.values()
        if context_key not in runtime_context
    ]
    if missing:
        raise ValueError(
            f"GA gene {gene.id!r} requires missing runtime context keys: "
            f"{', '.join(sorted(set(missing)))}."
        )
    return {
        param_name: runtime_context[context_key]
        for param_name, context_key in gene.runtime_args.items()
    }


def import_symbol(import_path: str):
    module_name, symbol_name = import_path.rsplit(".", 1)
    module = importlib.import_module(module_name)
    return getattr(module, symbol_name)


def import_fresh_module(module_name: str):
    for name in sorted(sys.modules, reverse=True):
        if name == module_name or name.startswith(f"{module_name}."):
            del sys.modules[name]
    return importlib.import_module(module_name)


def normalize_gene(raw_gene: Any) -> GeneDefinition:
    if isinstance(raw_gene, GeneDefinition):
        return raw_gene
    if isinstance(raw_gene, dict):
        return GeneDefinition(**raw_gene)
    raise TypeError(f"Unsupported GA gene definition: {type(raw_gene)!r}.")


def title_for_group(group: str) -> str:
    return {
        "pre_selection": "Pre-selection",
        "signal": "Signal",
        "allocation": "Allocation",
    }[group]
