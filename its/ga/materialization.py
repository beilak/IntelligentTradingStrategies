from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from its.ga.registry import build_component, get_gene
from its.ga.types import GeneDefinition
from its.strategies.core.types.strategy_types import Pipeline, Strategy

MODELS_DIR = Path("its/strategies/models")
MODELS_INIT = MODELS_DIR / "__init__.py"


@dataclass(frozen=True, slots=True)
class ComponentRender:
    step_name: str
    expression: str
    imports: tuple[str, ...] = ()
    constants: tuple[str, ...] = ()
    helper_code: str = ""


def build_strategy_from_gene_ids(
    asset_universe_prices,
    *,
    selector_id: str,
    signal_id: str,
    allocation_id: str,
    strategy_name: str,
    description: str,
) -> Strategy:
    selector = get_gene("pre_selection", selector_id)
    signal = get_gene("signal", signal_id)
    allocation = get_gene("allocation", allocation_id)
    steps = [
        (
            "pre_selection",
            build_component(selector, asset_universe_prices=asset_universe_prices),
        ),
        (
            "signal",
            build_component(signal, asset_universe_prices=asset_universe_prices),
        ),
        (
            "allocation",
            build_component(allocation, asset_universe_prices=asset_universe_prices),
        ),
    ]
    return Strategy(
        name=strategy_name,
        description=description,
        pipeline=Pipeline(steps=steps),
    )


def materialize_top_strategies(
    *,
    run_id: str,
    top_rows: list[dict[str, Any]],
    top_n: int = 3,
) -> list[dict[str, str]]:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    materialized = []
    class_names = []

    for rank, row in enumerate(top_rows[:top_n], start=1):
        class_name = f"Generated{safe_class_part(run_id)}Top{rank}Builder"
        module_name = f"ga_generated_{safe_file_part(run_id)}_top_{rank}"
        file_path = MODELS_DIR / f"{module_name}.py"
        file_path.write_text(
            render_strategy_module(class_name=class_name, row=row),
            encoding="utf-8",
        )
        materialized.append(
            {
                "rank": str(rank),
                "class_name": class_name,
                "module_name": f"its.strategies.models.{module_name}",
                "file_path": str(file_path),
            }
        )
        class_names.append((module_name, class_name))

    update_models_init(class_names)
    return materialized


def render_strategy_module(*, class_name: str, row: dict[str, Any]) -> str:
    generated_at = datetime.now(UTC).isoformat()
    strategy_name = row.get("strategy_name") or f"GA Strategy {class_name}"
    description = (
        f"GA materialized strategy. Selector={row['selector_name']}; "
        f"Signal={row['signal_name']}; Allocation={row['allocation_name']}; "
        f"TOTAL_SCORE={row.get('TOTAL_SCORE')}."
    )
    selector_gene = get_gene("pre_selection", str(row["selector_name"]))
    signal_gene = get_gene("signal", str(row["signal_name"]))
    allocation_gene = get_gene("allocation", str(row["allocation_name"]))
    components = [
        render_static_component(selector_gene),
        render_static_component(signal_gene),
        render_static_component(allocation_gene),
    ]

    imports = sorted({item for component in components for item in component.imports})
    constants = [item for component in components for item in component.constants]
    helper_code = "\n\n".join(
        dict.fromkeys(
            component.helper_code
            for component in components
            if component.helper_code.strip()
        )
    )
    constants_block = "\n".join(f"    {item}" for item in constants)
    if constants_block:
        constants_block = f"\n{constants_block}\n"
    steps_block = ",\n".join(
        render_pipeline_step(component) for component in components
    )
    helper_block = f"\n\n{helper_code}" if helper_code else ""
    module_imports = [item for item in imports if item.startswith("import ")]
    from_imports = [item for item in imports if item.startswith("from ")]
    import_lines = ["from typing import override"]
    if module_imports:
        import_lines.extend(["", *module_imports])
    import_lines.extend(
        [
            "",
            *from_imports,
            "from its.strategies.core.types.strategy_types import Pipeline, Strategy, StrategyBuilder",
        ]
    )
    import_block = "\n".join(import_lines)

    return f'''{import_block}{helper_block}


class {class_name}(StrategyBuilder):
    """Materialized GA strategy generated at {generated_at}."""
{constants_block}
    @override
    def build(self) -> Strategy:
        return Strategy(
            name={strategy_name!r},
            description={description!r},
            pipeline=Pipeline(
                steps=[
{steps_block}
                ]
            ),
        )
'''


def render_static_component(gene: GeneDefinition) -> ComponentRender:
    component_path = gene.resolved_component_path()
    if component_path:
        return render_declarative_component(gene, component_path)

    return render_legacy_factory_component(gene)


def render_declarative_component(
    gene: GeneDefinition,
    component_path: str,
) -> ComponentRender:
    component_name = import_name(component_path)
    component_expression = render_constructor(
        component_name,
        kwargs=gene.component_kwargs,
        asset_universe_arg=gene.asset_universe_arg,
    )
    imports = [import_line(component_path)]

    wrapper_path = gene.resolved_wrapper_path()
    if wrapper_path:
        wrapper_name = import_name(wrapper_path)
        imports.append(import_line(wrapper_path))
        expression = render_constructor(
            wrapper_name,
            kwargs=gene.wrapper_kwargs,
            positional_args=(component_expression,),
        )
    else:
        expression = component_expression

    return ComponentRender(
        step_name=step_name_for_group(gene.group),
        imports=tuple(dict.fromkeys(imports)),
        expression=expression,
    )


def render_legacy_factory_component(gene: GeneDefinition) -> ComponentRender:
    kwargs = gene.factory_kwargs
    if gene.factory_path == "its.ga.factories.turnover_selector":
        return ComponentRender(
            step_name="pre_selection",
            imports=(
                "from its.strategies.core.selectors import IntradayTurnoverSelector",
            ),
            constants=(
                f"TURNOVER_LOOKBACK_BARS = {format_literal(kwargs.get('lookback_bars', 10))}",
                f"MIN_TURNOVER_RUB = {format_literal(kwargs.get('min_turnover', 1_000_000))}",
            ),
            expression="""IntradayTurnoverSelector(
    asset_universe_prices=self._asset_universe_prices,
    lookback_bars=self.TURNOVER_LOOKBACK_BARS,
    min_turnover=self.MIN_TURNOVER_RUB,
    allow_empty_selection=False,
)""",
        )
    if gene.factory_path == "its.ga.factories.pass_through_signal":
        return ComponentRender(
            step_name="signal",
            imports=(
                "import numpy as np",
                "import sklearn.base as skb",
                "import sklearn.feature_selection as skf",
                "import sklearn.utils.validation as skv",
            ),
            helper_code=PASS_THROUGH_SELECTOR_CODE,
            expression="_KeepAllSelector()",
        )
    if gene.factory_path == "its.ga.factories.safe_trend_signal":
        return ComponentRender(
            step_name="signal",
            imports=(
                "from its.strategies.core.selectors import SafeEmptySelector, TrendSelector",
            ),
            constants=(f"SIGNAL_WINDOW = {format_literal(kwargs.get('window', 20))}",),
            expression="SafeEmptySelector(TrendSelector(window=self.SIGNAL_WINDOW))",
        )
    if gene.factory_path == "its.ga.factories.safe_trend_threshold_signal":
        return ComponentRender(
            step_name="signal",
            imports=(
                "from its.strategies.core.selectors import SafeEmptySelector, TrendThresholdSelector",
            ),
            constants=(
                f"SIGNAL_WINDOW = {format_literal(kwargs.get('window', 20))}",
                f"SIGNAL_SLOPE_THRESHOLD = {format_literal(kwargs.get('slope_threshold', 0.0))}",
            ),
            expression=(
                "SafeEmptySelector(\n"
                "    TrendThresholdSelector(\n"
                "        window=self.SIGNAL_WINDOW,\n"
                "        slope_threshold=self.SIGNAL_SLOPE_THRESHOLD,\n"
                "    )\n"
                ")"
            ),
        )
    if gene.factory_path == "its.ga.factories.equal_weighted_allocator":
        return ComponentRender(
            step_name="allocation",
            imports=("from its.strategies.core.optimization import EqualWeighted",),
            expression="EqualWeighted()",
        )
    if gene.factory_path == "its.ga.factories.inverse_volatility_allocator":
        return ComponentRender(
            step_name="allocation",
            imports=("from its.strategies.core.optimization import InverseVolatility",),
            expression="InverseVolatility(raise_on_failure=False)",
        )
    raise ValueError(
        f"Static materialization is not configured for GA gene {gene.id!r}."
    )


def render_constructor(
    name: str,
    *,
    kwargs: dict[str, Any],
    asset_universe_arg: str | None = None,
    positional_args: tuple[str, ...] = (),
) -> str:
    named_args = []
    if asset_universe_arg:
        named_args.append((asset_universe_arg, "self._asset_universe_prices"))
    named_args.extend((key, format_literal(value)) for key, value in kwargs.items())
    if not positional_args and not named_args:
        return f"{name}()"

    lines = []
    for positional_arg in positional_args:
        lines.append(f"{indent_block(positional_arg, 4)},")
    for key, value in named_args:
        lines.append(f"    {key}={value},")
    return f"{name}(\n" + "\n".join(lines) + "\n)"


def import_line(import_path: str) -> str:
    module_name, symbol_name = import_path.rsplit(".", 1)
    return f"from {module_name} import {symbol_name}"


def import_name(import_path: str) -> str:
    return import_path.rsplit(".", 1)[1]


def step_name_for_group(group: str) -> str:
    return {
        "pre_selection": "pre_selection",
        "signal": "signal",
        "allocation": "allocation",
    }[group]


def render_pipeline_step(component: ComponentRender) -> str:
    return (
        "                    (\n"
        f"                        {component.step_name!r},\n"
        f"{indent_block(component.expression, 24)}\n"
        "                    )"
    )


def indent_block(value: str, spaces: int) -> str:
    prefix = " " * spaces
    return "\n".join(f"{prefix}{line}" for line in value.splitlines())


def format_literal(value: Any) -> str:
    if isinstance(value, int) and abs(value) >= 1000:
        return f"{value:_}"
    return repr(value)


PASS_THROUGH_SELECTOR_CODE = '''class _KeepAllSelector(skb.BaseEstimator, skf.SelectorMixin):
    """Pass-through selector used as a neutral GA signal."""

    def fit(self, X, y=None):
        X = skv.validate_data(self, X, ensure_all_finite="allow-nan")
        self.to_keep_ = np.ones(X.shape[1], dtype=bool)
        return self

    def _get_support_mask(self):
        skv.check_is_fitted(self)
        return self.to_keep_

    def __sklearn_tags__(self):
        tags = super().__sklearn_tags__()
        tags.input_tags.allow_nan = True
        return tags'''


def update_models_init(class_names: list[tuple[str, str]]) -> None:
    existing = MODELS_INIT.read_text(encoding="utf-8") if MODELS_INIT.exists() else ""
    imports = extract_model_imports(existing)
    exports = parse_all(existing)
    if exports:
        module_by_class = {
            class_name: module_name for module_name, class_name in imports
        }
        imports = [
            (module_by_class[class_name], class_name)
            for class_name in exports
            if class_name in module_by_class
        ] + [item for item in imports if item[1] not in exports]

    for module_name, class_name in class_names:
        if (module_name, class_name) not in imports:
            imports.append((module_name, class_name))

    lines: list[str] = []
    for module_name, imported_names in group_imports(imports):
        if len(imported_names) == 1:
            lines.append(
                f"from its.strategies.models.{module_name} import {imported_names[0]}"
            )
            continue
        lines.append(f"from its.strategies.models.{module_name} import (")
        for imported_name in imported_names:
            lines.append(f"    {imported_name},")
        lines.append(")")

    exported_names = [class_name for _, class_name in imports]
    lines.append("")
    lines.append("__all__ = [")
    for exported_name in exported_names:
        lines.append(f"    {exported_name!r},")
    lines.append("]")
    lines.append("")
    MODELS_INIT.write_text("\n".join(lines), encoding="utf-8")


def extract_model_imports(source: str) -> list[tuple[str, str]]:
    imports: list[tuple[str, str]] = []
    module_name: str | None = None

    for raw_line in source.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if module_name is not None:
            if line == ")":
                module_name = None
                continue
            imported_name = line.rstrip(",")
            if imported_name:
                imports.append((module_name, imported_name))
            continue
        match = re.match(
            r"from its\.strategies\.models\.([a-zA-Z0-9_]+) import \($",
            line,
        )
        if match:
            module_name = match.group(1)
            continue
        match = re.match(
            r"from its\.strategies\.models\.([a-zA-Z0-9_]+) import ([a-zA-Z0-9_]+)$",
            line,
        )
        if match:
            imports.append((match.group(1), match.group(2)))

    unique_imports: list[tuple[str, str]] = []
    for item in imports:
        if item not in unique_imports:
            unique_imports.append(item)
    return unique_imports


def group_imports(imports: list[tuple[str, str]]) -> list[tuple[str, list[str]]]:
    grouped: list[tuple[str, list[str]]] = []
    for module_name, class_name in imports:
        for existing_module, class_names in grouped:
            if existing_module == module_name:
                if class_name not in class_names:
                    class_names.append(class_name)
                break
        else:
            grouped.append((module_name, [class_name]))
    return grouped


def parse_all(source: str) -> list[str]:
    try:
        module = ast.parse(source)
    except SyntaxError:
        return []
    for node in module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    try:
                        value = ast.literal_eval(node.value)
                    except (SyntaxError, ValueError):
                        return []
                    if isinstance(value, list):
                        return [str(item) for item in value]
    return []


def safe_file_part(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_]+", "_", value.lower())
    return normalized.strip("_") or "run"


def safe_class_part(value: str) -> str:
    return "".join(part.capitalize() for part in safe_file_part(value).split("_"))
