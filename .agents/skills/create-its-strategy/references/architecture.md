# ITS strategy architecture

## Data flow

`StrategyBuilder.build()` returns the frozen `Strategy(name, description, pipeline)` dataclass. The sklearn `Pipeline` normally contains:

1. a pre-selector narrowing the initial universe;
2. a signal selecting assets from that subset;
3. an optional row-window transformer;
4. a skfolio-compatible allocator producing a portfolio with `weights_dict`.

Backtesting builds close returns up to the rebalance date, fits the pipeline, predicts weights, and maps them back to all price columns. A fitted selector with no assets becomes a zero-weight rebalance in the engine.

## Component contracts

### Pre-selector

- Extend `its.strategies.core.types.selectors_types.Selectros`.
- Implement clone-compatible `__init__` and `fit(X, y=None)`.
- Set `to_keep_` to one boolean per input column.
- Put long-form context in an explicit constructor parameter such as `asset_universe_prices` or `_assets_info` in the builder.
- Export from `its.strategies.core.selectors`.

### Signal

- Extend `its.strategies.core.types.signals_types.Siglans`.
- Use returns-matrix `X` when the formula needs only historical returns.
- Use explicit long-form context for OHLCV, turnover, dividends, or metadata.
- Store diagnostic fitted series such as scores, thresholds, observations used, or forecasts.
- Export from `its.strategies.core.signals`.

### Allocator

- Prefer an existing allocator from `its.strategies.core.optimization` or skfolio.
- A custom allocator must be a sklearn/skfolio-compatible estimator whose fitted prediction exposes `weights_dict`.
- Define behavior for zero variance, singular covariance, infeasible optimization, and one-asset inputs.
- Export from `its.strategies.core.optimization`.

### Ready model

- Extend `StrategyBuilder`; accept runtime data through the inherited constructor.
- Express configurable strategy choices as uppercase class constants unless runtime configuration is explicitly required.
- Use a globally unique builder class name and descriptive strategy name.
- Export from `its.strategies.models.__init__`; registry discovery is based on public imports.

## Time and price context

`_limit_pipeline_price_context` keeps a full source copy and exposes rows only through the current training end. A component must use the context assigned to it at fit time and must not retain a permanently shortened private copy.

Backtest training data ends before the rebalance/execution row. Unit tests must prove that appending future candles cannot change an earlier fitted decision.

## Repository conventions

- Python 3.12, Black defaults, isort, Ruff, explicit type hints at boundaries.
- Source: `its/strategies/core/{selectors,signals,optimization}` and `its/strategies/models`.
- Tests: `tests/strategies_model/{selectors,signals,optimization,model}`.
- Use existing misspelled base types `Selectros` and `Siglans`; do not introduce aliases as part of unrelated work.

