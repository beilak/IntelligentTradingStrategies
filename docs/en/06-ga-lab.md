# GA Lab

[Back to Contents](README.md)

GA Lab is the subsystem for automatic trading-strategy generation using genetic algorithms.

![GA Lab UI](../img/GA_ui.png)

## Purpose

GA Lab uses already-created system components as gene alphabets:

```text
pre-selection gene + signal gene + allocation gene = candidate strategy
```

The genetic algorithm explores combinations, evaluates them on historical data, and saves the best strategies into the codebase.

## Main Files

| Path | Purpose |
| --- | --- |
| `its/services/ga_backend` | GA FastAPI backend |
| `its/ui/ga-ui` | GA Lab Vue UI |
| `its/ga/engine.py` | main GA engine |
| `its/ga/registry.py` | alphabet loading |
| `its/ga/types.py` | `GeneDefinition` description |
| `its/ga/materialization.py` | Python strategy-file generation |
| `its/ga/alphabets` | gene alphabets |
| `its/strategies/models` | destination for TOP strategies |

## Alphabets

The system has three gene groups.

### Pre-selection

Path:

```text
its/ga/alphabets/pre_selection
```

Current examples:

- `DividendHistorySelector`;
- `CrossSectionalMomentumSelector`;
- `sector_it_telecom`;
- `sector_energy_telecom`;
- `turnover_1m_10`;
- `turnover_25m_20`.

### Signal

Path:

```text
its/ga/alphabets/signal
```

Current examples:

- `pass_signal`;
- `PriceBreakoutSignal`;
- `SMACrossSignal`;
- `TwoCandlePositiveTrendSignal`.

### Allocation

Path:

```text
its/ga/alphabets/allocation
```

Current examples:

- `equal_weighted`;
- `inverse_volatility`;
- `HierarchicalRiskParity`;
- `CVaR`;
- `CVaRHighRisk`.

## Search Space

The search-space size is the product of gene counts:

```text
N(pre-selection) * N(signal) * N(allocation)
```

Each candidate is encoded by three indexes:

```text
(selector_idx, signal_idx, allocation_idx)
```

After decoding, the candidate gets a name:

```text
[GA][selector_name][signal_name][allocation_name]
```

## GA Settings

UI settings:

| Parameter | Purpose |
| --- | --- |
| `test_name` | run name |
| `start_date`, `end_date` | data period |
| `interval` | candle interval |
| `class_code` | asset class, for example `TQBR` |
| `test_size` | out-of-sample fraction |
| `num_generations` | number of generations |
| `sol_per_pop` | population size |
| `num_parents_mating` | number of parents |
| `mutation_probability` | mutation probability |
| `parent_selection_type` | parent selection method |
| `k_tournament` | tournament size |
| `keep_parents` | parent preservation |
| `keep_elitism` | number of elite solutions |
| `crossover_type` | crossover type |
| `mutation_type` | mutation type |
| `stop_criteria` | PyGAD early stop |
| `random_seed` | reproducibility |
| `cpcv_n_folds` | CPCV folds inside evaluation |
| `cpcv_n_test_folds` | CPCV test folds |
| `wf_train_size` | WalkForward train rows |
| `wf_test_size` | WalkForward test rows |
| `wf_purged_size` | purge rows |
| `top_n` | number of best strategies to return |
| `materialize_top` | create files for TOP strategies |

## Candidate Evaluation

Each candidate strategy is built as:

```text
ga_pre_selection -> ga_signal -> ga_allocation
```

The GA engine:

1. Loads data through Data Backend.
2. Builds the return matrix.
3. Splits the period into train and test.
4. Fits the pipeline on train.
5. Evaluates the candidate on test through CPCV and WalkForward.
6. Extracts metrics.
7. Computes `TOTAL_SCORE`.

## Fitness Metrics

Current metrics:

| Metric | Direction | Weight |
| --- | --- | --- |
| `WF_Return` | higher is better | `0.30` |
| `WF_Calmar` | higher is better | `0.30` |
| `Robustness_Delta` | lower is better | `0.20` |
| `Sharpe_Stability` | lower is better | `0.20` |

Penalties are also applied:

- for max drawdown above the threshold;
- for overly narrow portfolios with too few active assets.

Final scale:

```text
TOTAL_SCORE = 100 * weighted_score - penalties
```

## Run Results

GA Lab displays:

- run status;
- generations;
- best score;
- average score;
- best candidate;
- population;
- TOP strategies;
- materialized files;
- materialization errors if any.

## Strategy Materialization

If `materialize_top` is enabled, TOP-N strategies are saved to:

```text
its/strategies/models
```

Each candidate creates a Python file:

```text
ga_generated_<run_id>_top_<rank>.py
```

The file:

```text
its/strategies/models/__init__.py
```

is also updated. The generated strategy then appears in Strategy Lab as a regular registered model.

## Run Caches

GA runs are saved as JSON under:

```text
/app/its/data/ga_runs
```

Docker Compose persists them in:

```text
ga-cache
```

## Practical Workflow

1. The modeler creates selectors, signals, and allocators.
2. Adds them to GA alphabets.
3. Opens GA Lab.
4. Configures the period, population size, and generation count.
5. Runs evolution.
6. Reviews TOP strategies.
7. Materializes the best strategies.
8. Opens Strategy Lab.
9. Runs full CPCV, WalkForward, and Backtesting.
10. Compares new models with existing ones.

