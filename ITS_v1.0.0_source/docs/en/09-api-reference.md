# API and Integrations

[Back to Contents](README.md)

All external requests go through `nginx-gateway`. Paths below are available after launch on `localhost:8080`.

## Swagger

| API | URL |
| --- | --- |
| Data Backend | `/api/data/docs` |
| Strategy Backend | `/api/strategies/docs` |
| GA Backend | `/api/ga/docs` |

## Data API

Base path:

```text
/api/data/
```

### Health

```http
GET /api/data/health
```

Response:

```json
{"status":"ok"}
```

### Sources

```http
GET /api/data/sources
```

Returns connected sources and available resources.

### Stocks

```http
GET /api/data/stocks
```

Main parameters:

| Parameter | Description |
| --- | --- |
| `class_code` | instrument class, default `TQBR` |
| `search` | ticker or name search |
| `tickers` | ticker list |
| `exchange` | exchange filter |
| `sector` | sector filter |
| `country_of_risk` | country of risk |
| `limit`, `offset` | pagination |

### Currencies

```http
GET /api/data/currencies
```

Returns currency instruments.

### Prices

```http
GET /api/data/prices
```

Main parameters:

| Parameter | Description |
| --- | --- |
| `figis` | FIGI list |
| `tickers` | ticker list |
| `class_code` | instrument class |
| `instrument_type` | `stocks` or `currencies` |
| `start_date` | start date |
| `end_date` | end date |
| `interval` | candle interval |
| `is_complete` | completed candles only |

### Custom Gold Bars

```http
GET /api/data/custom-gold-bars
```

Additional parameters:

| Parameter | Description |
| --- | --- |
| `gold_ticker` | gold ticker, default `GLDRUB_TOM` |
| `gold_class_code` | gold class, default `CETS` |
| `count` | number of gold units |
| `bar_type` | gold bar type |

### Dividends

```http
GET /api/data/dividends
```

Parameters:

- `figis`;
- `tickers`;
- `class_code`;
- `start_date`;
- `end_date`.

## Strategy API

Base path:

```text
/api/strategies/
```

### Health

```http
GET /api/strategies/health
```

### Registry

```http
GET /api/strategies/registry
```

Returns groups:

- `pre_selection`;
- `signal_model`;
- `allocation`;
- `strategy_model`;
- `trading_strategy_model`.

### Core Models

```http
GET /api/strategies/models
GET /api/strategies/models/{model_name}
```

The detail endpoint returns:

- model description;
- pipeline composition;
- component groups;
- available reports.

### Full Trading Strategies

```http
GET /api/strategies/trading-strategies
GET /api/strategies/trading-strategies/{strategy_name}
```

### CPCV

```http
GET  /api/strategies/models/{model_name}/cpcv/tests
GET  /api/strategies/models/{model_name}/cpcv/tests/{test_name}
POST /api/strategies/models/{model_name}/cpcv/run
```

POST body:

```json
{
  "test_name": "baseline",
  "start_date": "2023-01-01",
  "end_date": "2025-12-31",
  "interval": "CANDLE_INTERVAL_DAY",
  "class_code": "TQBR",
  "n_folds": 10,
  "n_test_folds": 6
}
```

### WalkForward

```http
GET  /api/strategies/models/{model_name}/walk-forward/tests
GET  /api/strategies/models/{model_name}/walk-forward/tests/{test_name}
POST /api/strategies/models/{model_name}/walk-forward/run
```

POST body:

```json
{
  "test_name": "baseline",
  "start_date": "2023-01-01",
  "end_date": "2025-12-31",
  "interval": "CANDLE_INTERVAL_DAY",
  "class_code": "TQBR",
  "test_size": 0.33,
  "train_size_months": 3,
  "freq_months": 3,
  "wf_test_size": 1
}
```

### Backtesting

```http
GET  /api/strategies/models/{model_name}/backtest/tests
GET  /api/strategies/models/{model_name}/backtest/tests/{test_name}
POST /api/strategies/models/{model_name}/backtest/run
```

POST body:

```json
{
  "test_name": "baseline",
  "start_date": "2023-01-01",
  "end_date": "2025-12-31",
  "interval": "CANDLE_INTERVAL_DAY",
  "class_code": "TQBR",
  "trading_start_date": "2023-06-01",
  "rebalance_freq": "3ME",
  "rebalance_on": "last",
  "init_cash": 1000000,
  "fees": 0.0008,
  "slippage": 0.0,
  "freq": "1D",
  "rolling_window": 252,
  "tax_rate": 0.13
}
```

### Full Trading Strategy Backtesting

```http
GET  /api/strategies/trading-strategies/{strategy_name}/backtest/tests
GET  /api/strategies/trading-strategies/{strategy_name}/backtest/tests/{test_name}
POST /api/strategies/trading-strategies/{strategy_name}/backtest/run
```

### Comparison

```http
GET /api/strategies/comparison/latest
```

## GA API

Base path:

```text
/api/ga/
```

### Health

```http
GET /api/ga/health
```

### Alphabets

```http
GET /api/ga/alphabets
```

Returns gene groups and search-space size.

### Runs

```http
GET /api/ga/runs
GET /api/ga/runs/{run_id}
POST /api/ga/runs
```

POST body example:

```json
{
  "test_name": "ga_baseline",
  "start_date": "2023-01-01",
  "end_date": "2025-12-31",
  "interval": "CANDLE_INTERVAL_DAY",
  "class_code": "TQBR",
  "test_size": 0.33,
  "num_generations": 10,
  "sol_per_pop": 8,
  "num_parents_mating": 4,
  "mutation_probability": 0.25,
  "parent_selection_type": "tournament",
  "k_tournament": 3,
  "keep_parents": 0,
  "keep_elitism": 1,
  "crossover_type": "uniform",
  "mutation_type": "random",
  "stop_criteria": "saturate_3",
  "random_seed": 42,
  "cpcv_n_folds": 4,
  "cpcv_n_test_folds": 2,
  "wf_train_size": 63,
  "wf_test_size": 21,
  "wf_purged_size": 5,
  "top_n": 3,
  "materialize_top": true
}
```

## Integration Dependency

Strategy Backend and GA Backend do not call T-Invest directly. They obtain data through Data Backend. This reduces coupling and makes it possible to replace the data source without rewriting tests and GA.

