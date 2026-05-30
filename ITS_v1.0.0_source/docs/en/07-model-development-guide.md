# Modeler and Component Developer Guide

[Back to Contents](README.md)

This section describes how to extend the system with new data sources, model components, ready strategies, and GA genes.

## General Principle

The modeler should describe only the domain logic:

- how to select assets;
- how to form a signal;
- how to allocate weights;
- how to manage a position.

The platform handles infrastructure:

- data loading;
- matrix preparation;
- test execution;
- report construction;
- UI registration;
- result comparison;
- generation of new combinations through GA.

## Component Types

### Selector

A selector performs preliminary asset filtering.

Base type:

```text
its/strategies/core/types/selectors_types.py
```

The class should inherit from `Selectros` and implement `fit`. Inside `fit`, set:

```python
self.to_keep_ = ...
```

`to_keep_` is a boolean asset mask.

### Signal

A signal model performs additional selection after pre-selection.

Base type:

```text
its/strategies/core/types/signals_types.py
```

The class inherits from `Siglans` and also sets `to_keep_`.

### Allocation

An allocator defines portfolio weights. Current implementation uses skfolio allocators and custom extensions:

```text
its/strategies/core/optimization
```

An allocator should be compatible with the pipeline and produce weights through the skfolio interface.

## Creating a New Selector

1. Create a file under:

```text
its/strategies/core/selectors
```

2. Implement the class.

Minimal structure:

```python
import numpy as np
import sklearn.utils.validation as skv

from its.strategies.core.types.selectors_types import Selectros


class MySelector(Selectros):
    """Selector logic description."""

    def __init__(self, my_parameter: int = 10):
        self.my_parameter = my_parameter

    def fit(self, X, y=None):
        X = skv.validate_data(self, X, ensure_all_finite="allow-nan")
        self.to_keep_ = np.ones(X.shape[1], dtype=bool)
        return self
```

3. Add the class to:

```text
its/strategies/core/selectors/__init__.py
```

4. Add the class name to `__all__`.

After that, Strategy Backend can display the component in the registry.

## Creating a New Signal

1. Create a file under:

```text
its/strategies/core/signals
```

2. Inherit from `Siglans`.
3. Implement `fit`.
4. Add import and `__all__` entry in:

```text
its/strategies/core/signals/__init__.py
```

## Creating a New Allocator

1. Create or extend a file under:

```text
its/strategies/core/optimization
```

2. If skfolio is used, keep compatibility with `BaseOptimization`.
3. Export the allocator from:

```text
its/strategies/core/optimization/__init__.py
```

## Creating a Core Strategy Model

Ready models are stored in:

```text
its/strategies/models
```

A model should inherit from `StrategyBuilder`.

Example:

```python
from typing import override

from its.strategies.core.optimization import EqualWeighted
from its.strategies.core.selectors import IntradayTurnoverSelector
from its.strategies.core.types.strategy_types import Pipeline, Strategy, StrategyBuilder


class MyStrategyBuilder(StrategyBuilder):
    """Short strategy description."""

    @override
    def build(self) -> Strategy:
        return Strategy(
            name="MyStrategy",
            description="Model description",
            pipeline=Pipeline(
                steps=[
                    (
                        "pre_selection",
                        IntradayTurnoverSelector(
                            asset_universe_prices=self._asset_universe_prices,
                            lookback_bars=10,
                            min_turnover=1_000_000,
                        ),
                    ),
                    ("allocation", EqualWeighted()),
                ]
            ),
        )
```

Registration:

1. Import the class in `its/strategies/models/__init__.py`.
2. Add the class name to `__all__`.

The model will then appear in the Core Strategy tab.

## Creating a Full Trading Strategy

A full trading strategy is one level above the core: it adds position lifecycle rules.

Base types:

```text
its/strategies_model/core/trading_strategy.py
```

Inherit from `TradingStrategyBuilder` and implement:

- `name`;
- `description`;
- `build_core_strategy`;
- optionally `build_exit_policy`;
- optionally `build_metadata`.

Example:

```python
from typing import override

from its.strategies.models.top_turnover_eq import ModelTurnoverWithEQBuilder
from its.strategies_model.core.trading_strategy import (
    FixedStopTakeProfitPolicy,
    TradingStrategyBuilder,
)


class MyTradingStrategyBuilder(TradingStrategyBuilder):
    @property
    @override
    def name(self) -> str:
        return "MyTradingStrategy"

    @property
    @override
    def description(self) -> str:
        return "Core strategy with fixed stop loss and take profit."

    @override
    def build_core_strategy(self):
        return ModelTurnoverWithEQBuilder(
            self._asset_universe_prices,
            self._assets_info,
            self._runtime_context,
            self._dividends_info,
        ).build()

    @override
    def build_exit_policy(self):
        return FixedStopTakeProfitPolicy(
            stop_loss_pct=0.01,
            take_profit_pct=0.03,
        )
```

Register it in:

```text
its/strategies_model/model/__init__.py
```

## Adding a Component to GA

GA uses `GeneDefinition`.

File:

```text
its/ga/types.py
```

Minimal gene example:

```python
from its.ga.types import GeneDefinition
from its.strategies.core.signals import KeepAllSignal

GENES = [
    GeneDefinition(
        id="pass_signal",
        title="Pass-signal",
        description="Do not apply an additional signal filter.",
        group="signal",
        component=KeepAllSignal,
    )
]
```

Groups:

```text
pre_selection
signal
allocation
```

Genes are placed in:

```text
its/ga/alphabets/pre_selection
its/ga/alphabets/signal
its/ga/alphabets/allocation
```

If a component needs runtime data, use `runtime_args`:

```python
GeneDefinition(
    id="DividendHistorySelector",
    title="DividendHistorySelector",
    description="Select assets with dividend history.",
    group="pre_selection",
    component=DividendHistorySelector,
    wrapper=SafeEmptySelector,
    runtime_args={"dividends_df": "dividends_info"},
)
```

## GA Runtime Context

GA passes:

| Key | Content |
| --- | --- |
| `asset_universe_prices` | long candle table |
| `assets_info` | asset reference table |
| `dividends_info` | dividends |

## Component Recommendations

- Do not use future data when calculating features.
- Validate inputs and return clear errors.
- Use `SafeEmptySelector` if the component can select zero assets.
- Add docstrings: Strategy UI shows descriptions from code.
- Make parameters explicit in `__init__`.
- Do not change global state.
- Keep compatibility with pandas DataFrame and sklearn/skfolio pipeline.
- Cover new logic with tests.

## Testing New Components

Tests are located under:

```text
tests
```

Recommended commands:

```bash
poetry run pytest
poetry run ruff check .
poetry run mypy .
```

The current project includes tests for data loaders, selectors, signals, allocators, strategies, GA engine, and trading strategy backtesting.

