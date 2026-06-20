# API and Integrations

[Back to Contents](README.md)

All external requests go through `nginx-gateway`. Paths below are available after launch on `localhost:8080`.

## Swagger

| API | URL |
| --- | --- |
| Data Backend | `/api/data/docs` |
| Strategy Backend | `/api/strategies/docs` |
| GA Backend | `/api/ga/docs` |
| Execution Backend | `/api/execution/docs` |
| Tech System Backend | `/api/tech/docs` |
| Event Log Backend | `/api/event-log/docs` |

Most business endpoints require a JWT Bearer token obtained through Tech System (`POST /api/tech/auth/login` or `POST /api/tech/auth/register`). Health-check endpoints are available without business parameters.

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

### Unified Instrument Reference

```http
GET /api/data/instruments
```

Supports search and filters by `instrument_types`, `class_code`, `exchange`, `currency`, `api_trade_available`, `limit`, and `offset`.

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

### Monte Carlo and RSS

```http
GET  /api/data/monte-carlo
GET  /api/data/rss
GET  /api/data/rss/sources
POST /api/data/rss/load
```

`monte-carlo` builds close-price scenarios for one instrument. RSS endpoints read, filter, and load news from configured sources.

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

### Trading Strategy Production State

```http
GET /api/strategies/trading-strategies/prod-ready
PUT /api/strategies/trading-strategies/{strategy_name}/prod-ready
GET /api/strategies/strategy-type
```

These endpoints mark a trading strategy as ready for Execution, return production-ready strategies, and describe the full strategy type.

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

## Execution API

Base path:

```text
/api/execution/
```

### Health

```http
GET /api/execution/health
```

The response includes broker name, token status, configured account count, and `order_submission_mode`.

### Accounts and Overview

```http
GET /api/execution/accounts
GET /api/execution/accounts/{account_id}/overview?operations_days=30
```

Returns configured T-Invest accounts, portfolio, positions, withdrawal limits, margin attributes, active orders, stop orders, and operations.

### Orders

```http
POST /api/execution/accounts/{account_id}/orders
POST /api/execution/accounts/{account_id}/stop-orders
```

A regular order contains `instrument_id`, `side`, `order_type`, `quantity`, `price`, `time_in_force`, and comment. A stop order contains `stop_order_type`, `stop_price`, optional `limit_price`, and `expire_at`. In `stub` mode the ticket is validated locally and is not sent to the broker.

### Market Data and Strategies

```http
GET       /api/execution/market-data/last-price?instrument_id=...
WebSocket /api/execution/ws/orderbook
GET       /api/execution/accounts/{account_id}/strategies
PUT       /api/execution/accounts/{account_id}/strategies/{strategy_name}
DELETE    /api/execution/accounts/{account_id}/strategies/{strategy_name}
POST      /api/execution/accounts/{account_id}/strategies/{strategy_name}/runs
```

Strategy assignment is stored in the database. Runs use period, interval, `order_type`, `limit_offset_pct`, and `min_order_value` settings.

## Tech System API

Base path:

```text
/api/tech/
```

Main groups:

```http
POST /api/tech/auth/register
POST /api/tech/auth/login
POST /api/tech/auth/refresh
GET  /api/tech/auth/me
POST /api/tech/auth/logout
GET  /api/tech/profile/me
GET  /api/tech/roles
GET  /api/tech/permissions
GET  /api/tech/users
GET  /api/tech/role-requests
GET  /api/tech/audit/auth
GET  /api/tech/audit/roles
```

Tech System handles registration, JWT access/refresh tokens, roles, permissions, role requests, user blocking, and auth/RBAC audit events.

## Event Log API

Base path:

```text
/api/event-log/
```

```http
GET /api/event-log/health
GET /api/event-log/events
GET /api/event-log/events/filter-options
```

`events` supports filters `id`, `date_time_from`, `date_time_to`, `service`, `user`, `http_action`, `ip_address`, `path`, `header`, `body`, `limit`, and `offset`.

## Integration Dependency

Strategy Backend, GA Backend, and Execution Backend use Data Backend for market data. Execution Backend also calls the T-Invest broker API for accounts and orders. All backend services install Event Log and Observability middleware, and protected endpoints use JWT/RBAC from Tech System.
