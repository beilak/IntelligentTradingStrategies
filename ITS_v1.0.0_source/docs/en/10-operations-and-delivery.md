# Operations, Configuration, and Delivery

[Back to Contents](README.md)

## Delivery Package

A minimal system delivery includes:

- repository source code;
- `docker-compose.yml`;
- Dockerfiles for services;
- frontend applications;
- backend services;
- Python strategy core;
- GA engine;
- Markdown documentation in `docs`;
- PDF documentation versions in `docs/pdf`;
- interface screenshots in `docs/img`;
- tests in `tests`.

## Main Launch Command

```bash
docker compose up --build
```

This command is the main entry point for users and clients.

## PDF Documentation

Markdown files in `docs` are the primary editable documentation source. For handover as a single file, the system includes generated PDF versions:

- `docs/pdf/its_documentation_ru.pdf`;
- `docs/pdf/its_documentation_en.pdf`.

In the documentation web interface, the `PDF` button downloads the file for the currently selected interface language. After changing Markdown documentation, regenerate the PDF files with:

```bash
poetry run python scripts/build_docs_pdf.py
```

The script uses Markdown files and images from `docs/img`, builds Russian and English PDFs, and writes the result to `docs/pdf`.

## Environment Variables

| Variable | Purpose | Default |
| --- | --- | --- |
| `tinvest_token` | T-Invest token | empty |
| `TINVEST_TOKEN` | alternative token name | empty |
| `TINKOFF_INVEST_API_TOKEN` | alternative token name | empty |
| `DATA_BACKEND_STOCKS_TTL_MINUTES` | instrument-reference TTL | `30` |
| `DATA_BACKEND_BASE_URL` | Data Backend URL for internal services | set in compose |
| `STRATEGY_TEST_CACHE_DIR` | CPCV cache | `/app/its/data/strategy_tests/cpcv` |
| `STRATEGY_WF_CACHE_DIR` | WalkForward cache | `/app/its/data/strategy_tests/walk_forward` |
| `STRATEGY_BACKTEST_CACHE_DIR` | Backtesting cache | `/app/its/data/strategy_tests/backtest` |
| `GA_RUN_CACHE_DIR` | GA run cache | `/app/its/data/ga_runs` |
| `GA_MODELS_DIR` | strategy materialization directory | `/app/its/strategies/models` |
| `ITS_GATEWAY_PORT` | external gateway port | `8080` |

## Data Storage

Docker Compose uses volumes:

```text
t-invest-cache
strategy-test-cache
ga-cache
```

They preserve:

- loaded data across container restarts;
- expensive source responses;
- saved tests between sessions;
- GA run history.

## Materialized Strategies

GA Backend mounts:

```text
./its/strategies/models:/app/its/strategies/models
```

TOP strategies created by GA appear in the working copy as normal Python files.

Recommended steps after generation:

1. Review the generated file.
2. Check import in `its/strategies/models/__init__.py`.
3. Start Strategy Lab and verify the model is visible.
4. Run CPCV, WalkForward, and Backtesting.
5. Commit the changes if the model is accepted.

## Logs

Use Docker logs:

```bash
docker compose logs -f
docker compose logs -f data-backend
docker compose logs -f strategy-backend
docker compose logs -f ga-backend
```

## Updating the System

Recommended order:

1. Stop containers.
2. Pull or copy the new code version.
3. Check `.env`.
4. Run:

```bash
docker compose up --build
```

5. Check `/health` and UI.

## Backup

Important artifacts:

- `its/strategies/models` - generated strategies;
- Docker volume `strategy-test-cache` - saved tests;
- Docker volume `ga-cache` - GA runs;
- Docker volume `t-invest-cache` - data cache;
- `.env` - local secrets, should not be published.

## Security

The current configuration is intended for a local or closed research circuit.

Important:

- do not publish the T-Invest token;
- do not commit `.env`;
- do not expose the gateway to the public internet without authentication;
- note that backend CORS is permissive for development convenience;
- restrict server access if the system is deployed remotely.

## Current Limitations

The current version:

- is not a broker terminal;
- does not place real orders;
- does not execute exchange trades;
- does not guarantee future performance;
- depends on availability and quality of the external data source.

Production execution, risk limits, order journaling, and broker integration can be added as separate services.

## Client Handover

For handover, provide:

- repository or source-code archive;
- launch instructions;
- this documentation package;
- description of required tokens and access rights;
- known limitations;
- example test runs;
- list of base and generated strategies;
- demonstration CPCV, WalkForward, and Backtesting results.

## Acceptance Scenario

1. Create `.env` with the token.
2. Run `docker compose up --build`.
3. Open Launchpad.
4. Open Data Hub and load quotes for `SBER`.
5. Open Strategy Lab and select a base model.
6. Run a short Backtesting test.
7. Open GA Lab and view alphabets.
8. Run a small GA search with few generations.
9. Verify that a TOP strategy appears in `its/strategies/models`.
