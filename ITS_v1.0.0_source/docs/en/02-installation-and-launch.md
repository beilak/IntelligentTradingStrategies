# Installation, Prerequisites, and Launch

[Back to Contents](README.md)

## Minimum Requirements

For regular use, the user needs:

- Docker Engine or Docker Desktop;
- Docker Compose v2;
- Git to obtain the source code;
- internet access for image builds and data-source requests;
- a T-Invest API token for market data;
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

The token is required by Data Backend to retrieve instruments, quotes, currencies, and dividends from the T-Invest API.

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
- `launchpad-ui`;
- `nginx-gateway`.

## URLs After Launch

| Component | URL |
| --- | --- |
| Main screen | [http://localhost:8080/launchpad/](http://localhost:8080/launchpad/) |
| Data Hub | [http://localhost:8080/data/](http://localhost:8080/data/) |
| Strategy Lab | [http://localhost:8080/strategies/](http://localhost:8080/strategies/) |
| GA Lab | [http://localhost:8080/ga/](http://localhost:8080/ga/) |
| Documentation | [http://localhost:8080/docs/](http://localhost:8080/docs/) |
| Data API Swagger | [http://localhost:8080/api/data/docs](http://localhost:8080/api/data/docs) |
| Strategy API Swagger | [http://localhost:8080/api/strategies/docs](http://localhost:8080/api/strategies/docs) |
| GA API Swagger | [http://localhost:8080/api/ga/docs](http://localhost:8080/api/ga/docs) |

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

