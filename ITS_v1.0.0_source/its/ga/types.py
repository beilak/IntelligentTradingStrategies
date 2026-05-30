from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from typing import Any, Literal

AlphabetGroup = Literal["pre_selection", "signal", "allocation"]


@dataclass(frozen=True, slots=True)
class GeneDefinition:
    """A discrete GA gene available for strategy construction."""

    id: str
    title: str
    description: str
    group: AlphabetGroup
    component: Any | None = None
    component_path: str | None = None
    component_kwargs: dict[str, Any] = field(default_factory=dict)
    asset_universe_arg: str | None = None
    runtime_args: dict[str, str] = field(default_factory=dict)
    wrapper: Any | None = None
    wrapper_path: str | None = None
    wrapper_kwargs: dict[str, Any] = field(default_factory=dict)
    factory_path: str | None = None
    factory_kwargs: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        component_path = self.resolved_component_path()
        wrapper_path = self.resolved_wrapper_path()
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "group": self.group,
            "component_path": component_path,
            "component_kwargs": self.component_kwargs,
            "asset_universe_arg": self.asset_universe_arg,
            "runtime_args": self.runtime_args,
            "wrapper_path": wrapper_path,
            "wrapper_kwargs": self.wrapper_kwargs,
            "factory_path": self.factory_path,
            "factory_kwargs": self.factory_kwargs,
        }

    def resolved_component_path(self) -> str | None:
        if self.component_path:
            return self.component_path
        if self.component is None:
            return None
        return object_path(self.component)

    def resolved_wrapper_path(self) -> str | None:
        if self.wrapper_path:
            return self.wrapper_path
        if self.wrapper is None:
            return None
        return object_path(self.wrapper)


def object_path(value: Any) -> str:
    preferred_path = preferred_public_path(value)
    if preferred_path:
        return preferred_path
    module = getattr(value, "__module__", None)
    name = getattr(value, "__qualname__", None) or getattr(value, "__name__", None)
    if not module or not name:
        raise ValueError(f"Cannot build import path for GA component {value!r}.")
    return f"{module}.{name}"


def preferred_public_path(value: Any) -> str | None:
    name = getattr(value, "__name__", None)
    if not name:
        return None
    for module_name in (
        "its.strategies.core.selectors",
        "its.strategies.core.optimization",
    ):
        module = importlib.import_module(module_name)
        if getattr(module, name, None) is value:
            return f"{module_name}.{name}"
    return None
