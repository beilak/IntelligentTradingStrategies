---
name: create-its-strategy
description: Create or modify trading strategies and reusable pre-selectors, signals, and allocators in the IntelligentTradingStrategies repository. Use for Russian or English requests to design an ITS StrategyBuilder or pipeline component, register it, prevent look-ahead bias, support an empty cash portfolio, and add focused tests and backtest validation.
---

# Create ITS Strategy

Build repository-native strategy code without inventing parallel interfaces.

## Workflow

1. Read `references/architecture.md` completely.
2. Search for the closest existing component with `rg`; inspect its implementation, export, model composition, and tests.
3. Resolve the strategy contract before editing:
   - starting universe and pre-selection;
   - input shape: returns matrix or long OHLCV/metadata context;
   - lookback, thresholds, forecast horizon, and rebalance expectations;
   - allocator and its training window;
   - empty-selection behavior;
   - expected computational cost.
4. If a product choice materially changes behavior and is not stated or discoverable, ask one concise question. Otherwise make a conservative assumption and state it.
5. Select the nearest template from `assets/templates/`. Adapt it; never copy unused parameters or placeholder names.
6. Implement the smallest reusable component. Preserve current public APIs unless the user explicitly requests a breaking change.
7. Register public components in their package `__init__.py`; register ready builders in `its.strategies.models`.
8. Read `references/testing.md` completely and add the applicable tests.
9. Run focused pytest and Ruff. Run Black/isort only on touched Python files, then rerun tests and Ruff.
10. For a ready model, run a focused backtest smoke-test. Report assumptions, files changed, checks run, and any performance caveat.

## Required invariants

- Use only information available at the rebalance timestamp. Never read later candles or fit on the execution bar when the engine deliberately excludes it.
- Treat an empty selection as a valid all-cash portfolio with zero weights. Do not use `SafeEmptySelector` to force allocation.
- Keep sklearn estimators clone-compatible: assign every `__init__` argument unchanged to `self`, perform validation in `fit`, and suffix learned attributes with `_`.
- Produce a boolean `to_keep_` aligned with input columns for selectors/signals.
- Preserve DataFrame column names through the pipeline.
- For long price context, filter complete candles, coerce timestamps/numerics, require enough observations per asset, and calculate from the context already truncated by backtest.
- Do not catch broad exceptions. Catch only documented numerical/model-fit failures and expose useful fitted diagnostics.
- Bound expensive rolling training windows. Add controlled `n_jobs` only when independent assets can be evaluated safely.
- Avoid hardcoded tickers unless the strategy explicitly defines a fixed universe.

## Template routing

- Complete model: `assets/templates/strategy_builder.py`
- Pre-selector: `assets/templates/pre_selector.py`
- Signal from long OHLC context: `assets/templates/price_context_signal.py`
- Signal from returns matrix: `assets/templates/returns_signal.py`
- Allocator: `assets/templates/allocator.py`
- Unit test: `assets/templates/test_component.py`
- Pipeline/backtest smoke-test: `assets/templates/test_strategy_backtest.py`

Templates are starting points, not files to copy verbatim. Remove unused branches and replace every `Example`/`TODO` marker.

