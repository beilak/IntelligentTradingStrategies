# Installation, Prerequisites, and Launch

[Back to Contents](README.md)

## Minimum Requirements

For regular use, the user needs:

- Docker Engine or Docker Desktop;
- Docker Compose v2;
- Git to obtain the source code;
- internet access for image builds and data-source requests;
- a T-Invest API token for market data;
- T-Invest broker account IDs for Execution, if the execution circuit is used;
- free port `8080`, or another port set through `ITS_GATEWAY_PORT`.

Recommended workstation resources:

- 4 CPU cores or more;
- 8 GB RAM or more;
- 5 GB of free space for images, caches, and test results.

## Development Requirements

If the system is developed locally in addition to Docker launch:

- Python `3.12.x`;
- Poetry;
- Node.js `20+`;
- npm;
- a modern browser.

Main backend libraries:

- FastAPI and Uvicorn for API services;
- pandas and NumPy for data processing;
- scikit-learn pipeline interfaces for components;
- skfolio for portfolio optimization and model selection;
- vectorbt for backtesting;
- PyGAD for genetic algorithms;
- httpx, aiohttp, aiometer, async-lru for HTTP and asynchronous loading;
- t-tech-investments for T-Invest integration.

Main frontend libraries:

- Vue 3;
- Vite;
- TypeScript;
- lucide-vue-next;
- ECharts in Data UI.

## Token Configuration

Create or update `.env` in the repository root:

```dotenv
tinvest_token=your_tinkoff_invest_token
```

Alternative names are also supported:

```dotenv
TINVEST_TOKEN=your_tinkoff_invest_token
TINKOFF_INVEST_API_TOKEN=your_tinkoff_invest_token
```

The token is required by Data Backend to retrieve instruments, quotes, currencies, and dividends from the T-Invest API. Execution uses `EXECUTION_TINVEST_TOKEN` when it is set; otherwise it uses the same token variables.

Execution accounts can be configured with:

```dotenv
EXECUTION_TINVEST_ACCOUNT_IDS=account_id_1,account_id_2
EXECUTION_TINVEST_ACCOUNTS=account_id_1:Main,account_id_2:IIS
EXECUTION_ORDER_SUBMISSION_MODE=stub
```

`EXECUTION_ORDER_SUBMISSION_MODE=stub` validates order tickets locally and does not send them to the broker. The default is `real`.

## Launching the Whole System

From the repository root:

```bash
docker compose up --build
```

This builds and starts:

- `data-backend`;
- `data-ui`;
- `strategy-backend`;
- `strategy-ui`;
- `ga-backend`;
- `ga-ui`;
- `execution-backend`;
- `execution-ui`;
- `tech-system-backend`;
- `tech-system-ui`;
- `event-log-backend`;
- `launchpad-ui`;
- PostgreSQL for application data and a separate PostgreSQL for event logs;
- `nginx-gateway`.

## URLs After Launch

| Component | URL |
| --- | --- |
| Main screen | [http://localhost:8080/launchpad/](http://localhost:8080/launchpad/) |
| Data Hub | [http://localhost:8080/data/](http://localhost:8080/data/) |
| Strategy Lab | [http://localhost:8080/strategies/](http://localhost:8080/strategies/) |
| GA Lab | [http://localhost:8080/ga/](http://localhost:8080/ga/) |
| Execution | [http://localhost:8080/execution/](http://localhost:8080/execution/) |
| Tech System / Auth | [http://localhost:8080/tech/auth/](http://localhost:8080/tech/auth/) |
| Documentation | [http://localhost:8080/docs/](http://localhost:8080/docs/) |
| Data API Swagger | [http://localhost:8080/api/data/docs](http://localhost:8080/api/data/docs) |
| Strategy API Swagger | [http://localhost:8080/api/strategies/docs](http://localhost:8080/api/strategies/docs) |
| GA API Swagger | [http://localhost:8080/api/ga/docs](http://localhost:8080/api/ga/docs) |
| Execution API Swagger | [http://localhost:8080/api/execution/docs](http://localhost:8080/api/execution/docs) |
| Tech API Swagger | [http://localhost:8080/api/tech/docs](http://localhost:8080/api/tech/docs) |
| Event Log API Swagger | [http://localhost:8080/api/event-log/docs](http://localhost:8080/api/event-log/docs) |

If port `8080` is occupied:

```bash
ITS_GATEWAY_PORT=8090 docker compose up --build
```

The main screen will then be available at:

```text
http://localhost:8090/launchpad/
```

## Health Checks

After startup, open:

```text
http://localhost:8080/health
```

Expected response:

```text
ok
```

API health checks:

```text
http://localhost:8080/api/data/health
http://localhost:8080/api/strategies/health
http://localhost:8080/api/ga/health
http://localhost:8080/api/execution/health
http://localhost:8080/api/tech/health
http://localhost:8080/api/event-log/health
```

Expected JSON:

```json
{"status":"ok"}
```

## Data and Caches

Docker Compose creates named volumes:

| Volume | Purpose |
| --- | --- |
| `t-invest-cache` | quote, reference-data, and dividend cache |
| `strategy-test-cache` | saved CPCV, WalkForward, and Backtesting reports |
| `ga-cache` | saved GA runs |
| `postgres-data` | users, roles, strategy assignments, and application state |
| `event-log-postgres-data` | user and API action event log |

GA also writes materialized strategies to:

```text
its/strategies/models
```

## Common Startup Issues

### T-Invest Token Is Not Set

Data Backend returns `503` with a message that `tinvest_token`, `TINVEST_TOKEN`, or `TINKOFF_INVEST_API_TOKEN` must be configured.

Resolution: check `.env` and restart containers.

### Port 8080 Is Occupied

Resolution:

```bash
ITS_GATEWAY_PORT=8090 docker compose up --build
```

### No Quotes for the Selected Period

Possible causes:

- instrument not found;
- period is too early;
- the source returned no candles;
- invalid `class_code` or instrument type.

Resolution: check ticker, FIGI, `class_code`, interval, and dates in Data Hub.

### GA Run Takes Too Long

Possible causes:

- large population;
- many generations;
- long data period;
- many assets;
- expensive CPCV or WalkForward settings.

Resolution: reduce `num_generations`, `sol_per_pop`, number of assets, or period length.

### Execution Does Not Show Accounts

Possible causes:

- T-Invest token is not set;
- `EXECUTION_TINVEST_ACCOUNT_IDS` or `EXECUTION_TINVEST_ACCOUNTS` is not set;
- the configured account is not returned by T-Invest API for the current token.

Resolution: check `.env`, token permissions, and restart containers.
