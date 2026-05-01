# Strategy Lab

[Back to Contents](README.md)

Strategy Lab is the main workspace for the financial modeler. It displays components, ready models, strategy composition, CPCV, WalkForward, Backtesting, and model comparison.

![Strategy Lab UI](../img/strategy_ui.png)

## Purpose

Strategy Lab is used to:

- inspect registered components;
- select ready models;
- understand model composition;
- run tests;
- read saved results;
- compare strategies;
- analyze portfolio composition and sector exposure.

## Main Files

| Path | Purpose |
| --- | --- |
| `services/strategy_backend` | Strategy Lab FastAPI backend |
| `ui/strategy-ui` | Strategy Lab Vue UI |
| `its/strategies/core` | strategy-core components |
| `its/strategies/models` | ready core models |
| `its/strategies/testing` | testing methods |
| `its/strategies_model` | full trading strategies |

## Strategy Structure

The strategy core consists of three sequential steps:

```text
pre-selection -> signal -> allocation
```

### Pre-selection

Initial asset filtering. The selector receives a price or return matrix and produces a mask of assets allowed for further processing.

Current examples:

- `IntradayTurnoverSelector` - turnover-based selection;
- `CrossSectionalMomentumSelector` - cross-sectional momentum selection;
- `DividendHistorySelector` - dividend-history selection;
- `SectorSelector` - sector-based selection;
- `TrendSelector` and `TrendThresholdSelector` - trend-based selection;
- `KeepAllSelector` - pass-through selection;
- `SafeEmptySelector` - wrapper that protects the pipeline from empty selection.

### Signal

The signal layer applies additional selection logic after pre-selection.

Examples:

- `KeepAllSignal` - passes all assets;
- `PriceBreakoutSignal` - selects assets breaking above a recent high;
- `SMACrossSignal` - moving-average cross signal;
- `TwoCandlePositiveTrendSignal` - positive movement over recent candles.

### Allocation

The allocator assigns portfolio weights to selected assets.

Examples:

- `EqualWeighted`;
- `InverseVolatility`;
- `HierarchicalRiskParity`;
- `CVaR`;
- `CVaRHighRisk`.

Allocators use skfolio and custom extensions.

## Strategy Lab Tabs

### Pre-selections

Displays registered selectors. Each item shows:

- class name;
- module;
- description;
- constructor signature;
- parameters;
- source path.

### Signal Models

Displays registered signal models with the same metadata.

### Allocation

Displays registered allocators.

### Core Strategy

The key tab. It displays models from:

```text
its/strategies/models
```

For a selected model the user sees:

- name;
- description;
- pipeline composition;
- available tests;
- saved report list;
- buttons to run CPCV, WalkForward, and Backtesting.

### Trading Strategy

A full trading strategy includes:

- portfolio-model core;
- entry and exit rules;
- stop-loss;
- take-profit;
- additional position lifecycle policies.

Current example:

```text
TurnoverEqStopLoss1TakeProfit3Builder
```

It uses `ModelTurnoverWithEQBuilder`, `1%` stop-loss, and `3%` take-profit.

## CPCV

CPCV opens in a separate modal window.

![CPCV test](../img/CPCV%20test.png)

The user sets:

- test name;
- start date;
- end date;
- interval;
- asset class;
- `n_folds`;
- `n_test_folds`.

Result:

- CPCV summary;
- metrics by test paths;
- cumulative-return path charts;
- asset list;
- saved JSON report.

## WalkForward

WalkForward opens in a separate modal window.

![WalkForward test](../img/WalkForward%20test.png)

The user sets:

- test name;
- data period;
- OOS test fraction;
- train window size in months;
- window shift frequency;
- WF test size;
- asset class and interval.

Result:

- WalkForward windows;
- metrics;
- individual window charts;
- stitched OOS equity curve;
- number of removed duplicate dates;
- saved JSON report.

## Backtesting

Backtesting opens in a separate modal window.

![Backtesting](../img/Backtesting.png)

The user sets:

- data period;
- trading start date;
- rebalance frequency;
- rebalance date rule;
- initial capital;
- fees;
- slippage;
- tax rate;
- rolling Sharpe window.

Result:

- equity curve;
- drawdown curve;
- rolling Sharpe;
- vectorbt metrics table;
- return and risk summary;
- portfolio weights at rebalances;
- stop-loss and take-profit events for full trading strategies.

### Portfolio Composition

Backtesting results include a portfolio-composition modal.

![Backtesting portfolio composition](../img/Backtesting%20portfolio%20composition.png)

Available details:

- securities included at each rebalance;
- each security weight;
- total weights;
- sector aggregation;
- sector exposure chart.

## Model Comparison

Model comparison opens in a separate modal.

![Model compare](../img/Model_compare.png)

The system takes the latest saved CPCV, WalkForward, and Backtesting results for each model and builds an aggregate ranking.

Metrics used:

- `WF_Return`;
- `WF_Calmar`;
- `Robustness_Delta`;
- `Sharpe_Stability`;
- Backtesting metric wins;
- `TOTAL_SCORE`.

A model enters comparison only if a full set of saved tests is available.

## Saved Results

Test results are saved as JSON caches:

| Type | Environment variable | Container path |
| --- | --- | --- |
| CPCV | `STRATEGY_TEST_CACHE_DIR` | `/app/its/data/strategy_tests/cpcv` |
| WalkForward | `STRATEGY_WF_CACHE_DIR` | `/app/its/data/strategy_tests/walk_forward` |
| Backtesting | `STRATEGY_BACKTEST_CACHE_DIR` | `/app/its/data/strategy_tests/backtest` |

Docker Compose persists them in `strategy-test-cache`.

