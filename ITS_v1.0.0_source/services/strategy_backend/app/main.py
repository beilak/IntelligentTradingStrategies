import ast
import dataclasses
import importlib
import inspect
import sys
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from services.strategy_backend.app.backtest import router as backtest_router
from services.strategy_backend.app.comparison import router as comparison_router
from services.strategy_backend.app.cpcv import router as cpcv_router
from services.strategy_backend.app.trading_strategy_backtest import (
    router as trading_strategy_backtest_router,
)
from services.strategy_backend.app.walk_forward import router as walk_forward_router


API_PREFIX = "/api/v1"

REGISTRIES = [
    {
        "id": "pre_selection",
        "title": "Pre-selections",
        "module": "its.strategies.core.selectors",
        "role": "Filters the starting asset universe before scoring and allocation.",
    },
    {
        "id": "signal_model",
        "title": "Signal Models",
        "module": "its.strategies.core.signals",
        "role": "Scores, ranks, predicts, or otherwise adjusts priorities of assets.",
    },
    {
        "id": "allocation",
        "title": "Allocation",
        "module": "its.strategies.core.optimization",
        "role": "Builds portfolio weights from the filtered/scored universe.",
    },
    {
        "id": "strategy_model",
        "title": "Ready Models",
        "module": "its.strategies.models",
        "role": "Complete model builders registered for modelers.",
    },
    {
        "id": "trading_strategy_model",
        "title": "Trading Strategies",
        "module": "its.strategies_model.model",
        "role": "Full trading strategies: portfolio core plus execution rules such as stop loss and take profit.",
    },
]


def create_app() -> FastAPI:
    app = FastAPI(
        title="ITS Strategy Backend",
        description="Strategy component registry API for Intelligent Trading Strategies",
        version="0.1.0",
        docs_url=f"{API_PREFIX}/docs",
        openapi_url=f"{API_PREFIX}/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(backtest_router, prefix=API_PREFIX)
    app.include_router(comparison_router, prefix=API_PREFIX)
    app.include_router(cpcv_router, prefix=API_PREFIX)
    app.include_router(trading_strategy_backtest_router, prefix=API_PREFIX)
    app.include_router(walk_forward_router, prefix=API_PREFIX)

    @app.get(f"{API_PREFIX}/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get(f"{API_PREFIX}/registry")
    async def registry() -> dict[str, Any]:
        groups = [load_registry_group(registry_info) for registry_info in REGISTRIES]
        return {
            "groups": groups,
            "models": next(
                group["items"] for group in groups if group["id"] == "strategy_model"
            ),
            "trading_strategies": next(
                group["items"]
                for group in groups
                if group["id"] == "trading_strategy_model"
            ),
            "strategy_type": describe_strategy_type(),
        }

    @app.get(f"{API_PREFIX}/models")
    async def models() -> dict[str, Any]:
        group = load_registry_group(get_registry_info("strategy_model"))
        return {"items": group["items"]}

    @app.get(f"{API_PREFIX}/models/{{model_name}}")
    async def model_detail(model_name: str) -> dict[str, Any]:
        model_group = load_registry_group(get_registry_info("strategy_model"))
        model_item = next(
            (item for item in model_group["items"] if item["name"] == model_name),
            None,
        )
        if model_item is None:
            raise HTTPException(status_code=404, detail="Model is not registered.")

        component_groups = [
            load_registry_group(info)
            for info in REGISTRIES
            if info["id"] != "strategy_model"
        ]
        model_obj = import_object(model_item["module"], model_item["name"])
        return {
            **model_item,
            "composition": inspect_model_composition(model_obj, component_groups),
            "component_groups": component_groups,
            "future_reports": [
                {"id": "cpcv", "title": "CPCV", "status": "available"},
                {"id": "walk_forward", "title": "WalkForward", "status": "available"},
                {"id": "backtesting", "title": "Backtesting", "status": "available"},
            ],
        }

    @app.get(f"{API_PREFIX}/trading-strategies")
    async def trading_strategies() -> dict[str, Any]:
        group = load_registry_group(get_registry_info("trading_strategy_model"))
        return {"items": group["items"]}

    @app.get(f"{API_PREFIX}/trading-strategies/{{strategy_name}}")
    async def trading_strategy_detail(strategy_name: str) -> dict[str, Any]:
        strategy_group = load_registry_group(
            get_registry_info("trading_strategy_model")
        )
        strategy_item = next(
            (item for item in strategy_group["items"] if item["name"] == strategy_name),
            None,
        )
        if strategy_item is None:
            raise HTTPException(
                status_code=404, detail="Trading strategy is not registered."
            )

        component_groups = [
            load_registry_group(get_registry_info("strategy_model")),
            load_registry_group(
                {
                    "id": "trading_policy",
                    "title": "Trading Policies",
                    "module": "its.strategies_model.core",
                    "role": "Position lifecycle policies used by full trading strategies.",
                }
            ),
        ]
        strategy_obj = import_object(strategy_item["module"], strategy_item["name"])
        return {
            **strategy_item,
            "composition": inspect_trading_strategy_composition(
                strategy_obj,
                component_groups,
            ),
            "component_groups": component_groups,
            "future_reports": [
                {"id": "backtesting", "title": "Backtesting", "status": "available"},
            ],
        }

    @app.get(f"{API_PREFIX}/strategy-type")
    async def strategy_type() -> dict[str, Any]:
        return describe_strategy_type()

    return app


def get_registry_info(registry_id: str) -> dict[str, str]:
    return next(info for info in REGISTRIES if info["id"] == registry_id)


def load_registry_group(registry_info: dict[str, str]) -> dict[str, Any]:
    module_name = registry_info["module"]
    module = import_fresh_module(module_name)
    names = list(getattr(module, "__all__", []))
    items = []

    for name in names:
        obj = getattr(module, name, None)
        if obj is None:
            items.append(
                {
                    "name": name,
                    "module": module_name,
                    "kind": "missing",
                    "status": "missing",
                    "description": "",
                    "signature": "",
                    "parameters": [],
                    "source_path": "",
                }
            )
            continue

        items.append(describe_object(obj, fallback_module=module_name))

    return {**registry_info, "items": items, "count": len(items)}


def import_fresh_module(module_name: str) -> Any:
    for name in sorted(sys.modules, reverse=True):
        if name == module_name or name.startswith(f"{module_name}."):
            del sys.modules[name]
    return importlib.import_module(module_name)


def describe_object(obj: Any, fallback_module: str | None = None) -> dict[str, Any]:
    return {
        "name": getattr(obj, "__name__", str(obj)),
        "module": getattr(obj, "__module__", fallback_module or ""),
        "kind": object_kind(obj),
        "status": "registered",
        "description": compact_doc(inspect.getdoc(obj) or ""),
        "signature": get_signature(obj),
        "parameters": get_parameters(obj),
        "source_path": get_source_path(obj),
    }


def object_kind(obj: Any) -> str:
    if inspect.isclass(obj):
        return "class"
    if inspect.isfunction(obj):
        return "function"
    return type(obj).__name__


def compact_doc(doc: str, limit: int = 700) -> str:
    paragraphs = [part.strip() for part in doc.split("\n\n") if part.strip()]
    text = paragraphs[0] if paragraphs else doc.strip()
    text = " ".join(line.strip() for line in text.splitlines() if line.strip())
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1].rstrip()}..."


def get_signature(obj: Any) -> str:
    target = obj.__init__ if inspect.isclass(obj) else obj
    try:
        signature = str(inspect.signature(target))
    except (TypeError, ValueError):
        return ""
    return signature.replace("(self, ", "(").replace("(self)", "()")


def get_parameters(obj: Any) -> list[dict[str, str]]:
    target = obj.__init__ if inspect.isclass(obj) else obj
    try:
        parameters = inspect.signature(target).parameters.values()
    except (TypeError, ValueError):
        return []

    result = []
    for parameter in parameters:
        if parameter.name == "self":
            continue
        result.append(
            {
                "name": parameter.name,
                "default": ""
                if parameter.default is inspect._empty
                else repr(parameter.default),
                "annotation": annotation_to_string(parameter.annotation),
                "kind": str(parameter.kind),
            }
        )
    return result


def annotation_to_string(annotation: Any) -> str:
    if annotation is inspect._empty:
        return ""
    return getattr(annotation, "__name__", str(annotation).replace("typing.", ""))


def get_source_path(obj: Any) -> str:
    try:
        return inspect.getsourcefile(obj) or ""
    except TypeError:
        return ""


def import_object(module_name: str, object_name: str) -> Any:
    module = importlib.import_module(module_name)
    return getattr(module, object_name)


def inspect_model_composition(
    model_obj: Any,
    component_groups: list[dict[str, Any]],
) -> dict[str, Any]:
    source = get_source(model_obj)
    registered_components = [
        item
        for group in component_groups
        for item in group["items"]
        if item["status"] == "registered" and item["name"] in source
    ]

    return {
        "steps": inspect_pipeline_steps(source, component_groups),
        "registered_components": registered_components,
        "source_excerpt": source,
    }


def inspect_trading_strategy_composition(
    strategy_obj: Any,
    component_groups: list[dict[str, Any]],
) -> dict[str, Any]:
    source = get_source(strategy_obj)
    helper_names = {
        "PositionContext",
        "PositionExitDecision",
        "PositionExitPolicy",
        "TradingStrategy",
        "TradingStrategyBuilder",
        "TradingStrategyProtocol",
    }
    registered_components = [
        item
        for group in component_groups
        for item in group["items"]
        if item["status"] == "registered"
        and item["name"] != getattr(strategy_obj, "__name__", "")
        and item["name"] not in helper_names
        and item["name"] in source
    ]

    return {
        "steps": [
            {
                "step": step_name_for_component(item, component_groups),
                "component": item["name"],
                "category": group_id_for_component(item, component_groups),
            }
            for item in registered_components
        ],
        "registered_components": registered_components,
        "source_excerpt": source,
    }


def group_id_for_component(
    component: dict[str, Any],
    component_groups: list[dict[str, Any]],
) -> str:
    for group in component_groups:
        if any(item["name"] == component["name"] for item in group["items"]):
            return group["id"]
    return "unknown"


def step_name_for_component(
    component: dict[str, Any],
    component_groups: list[dict[str, Any]],
) -> str:
    group_id = group_id_for_component(component, component_groups)
    if group_id == "strategy_model":
        return "core_strategy"
    if group_id == "trading_policy":
        return "exit_policy"
    return group_id


def get_source(obj: Any) -> str:
    try:
        return inspect.getsource(obj)
    except (OSError, TypeError):
        return ""


def inspect_pipeline_steps(
    source: str,
    component_groups: list[dict[str, Any]],
) -> list[dict[str, str]]:
    if not source:
        return []

    component_index = {
        item["name"]: group["id"]
        for group in component_groups
        for item in group["items"]
    }
    steps = []

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return steps

    for node in ast.walk(tree):
        if not isinstance(node, ast.Tuple) or len(node.elts) != 2:
            continue
        if not isinstance(node.elts[0], ast.Constant) or not isinstance(
            node.elts[0].value, str
        ):
            continue
        component_name = call_name(node.elts[1])
        if not component_name:
            continue
        steps.append(
            {
                "step": node.elts[0].value,
                "component": component_name,
                "category": component_index.get(component_name, "unknown"),
            }
        )

    return steps


def call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Call):
        return call_name(node.func)
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def describe_strategy_type() -> dict[str, Any]:
    from its.strategies.core.types.strategy_types import Strategy

    fields = []
    if dataclasses.is_dataclass(Strategy):
        fields = [
            {
                "name": field.name,
                "type": annotation_to_string(field.type),
                "default": ""
                if field.default is dataclasses.MISSING
                else repr(field.default),
            }
            for field in dataclasses.fields(Strategy)
        ]

    return {
        "name": "Strategy",
        "module": Strategy.__module__,
        "description": inspect.getdoc(Strategy) or "",
        "fields": fields,
    }


app = create_app()
