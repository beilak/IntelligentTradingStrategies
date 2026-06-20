# Repository Guidelines

## Project Structure & Module Organization

Core Python package code lives in `its/`, including GA, observability, event log, auth, execution, and shared configuration modules. Service wrappers and Dockerfiles are split between `services/*_backend/` and `its/services/*_backend/`, with FastAPI entrypoints under each `app/main.py`. Tests are organized by domain in `tests/` (`tests/ga/`, `tests/execution/`, `tests/tech_system/`). Frontend apps are Vue/Vite packages in `ui/*-ui/`. Product docs, diagrams, screenshots, and PDFs are in `docs/` and `doc/`; infrastructure config is under `infra/`.

## Build, Test, and Development Commands

- `poetry install` installs Python runtime and dev dependencies.
- `poetry run pytest` runs the full test suite.
- `poetry run pytest tests/ga/test_engine.py` runs a focused test file.
- `poetry run ruff check .`, `poetry run black .`, and `poetry run isort .` lint and format Python.
- `docker compose up --build` builds and starts the full local stack behind the nginx gateway.
- `docker compose --profile observability up --build` also starts the monitoring stack.
- `npm install && npm run build` from a specific `ui/*-ui/` directory type-checks and builds that frontend.
- `poetry run python scripts/build_docs_pdf.py` regenerates documentation PDFs.

## Coding Style & Naming Conventions

Use Python 3.12. Keep Python formatted with Black defaults, imports sorted with isort, and lint issues fixed with Ruff. Prefer explicit type hints for service boundaries and Pydantic schemas. Name Python modules and functions in `snake_case`, classes and Pydantic models in `PascalCase`, and constants in `UPPER_SNAKE_CASE`. Vue components should follow the existing single-file component pattern with TypeScript, local `api.ts` clients, and package-local styles.

## Testing Guidelines

Pytest is the backend test framework; `pytest-asyncio` is enabled with `asyncio_mode = auto`. Add tests near the relevant domain folder and name files `test_*.py`, with test functions `test_*`. Mock external broker, market data, and network dependencies; avoid requiring real T-Invest tokens. For frontend changes, run `npm run build` in the touched UI package.

## Commit & Pull Request Guidelines

Git history uses short, direct commit summaries such as `c4 diagrams`, `montecarlo modeling`, and `load data to correct range`. Keep commits focused and concise. Pull requests should state the user-facing change, list tests or builds run, mention configuration or migration impacts, and include screenshots for UI changes.

## Security & Configuration Tips

Keep secrets in `.env`; start from `.env.example` and do not commit real broker tokens, account IDs, passwords, or DSNs. Prefer environment variables documented in `README.md`.
