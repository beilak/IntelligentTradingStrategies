# ISSAT

Intelligent system for securities analysis and trading.

## Быстрый старт

Создай или обнови `.env` в корне проекта:

```dotenv
tinvest_token=your_tinkoff_invest_token
EXECUTION_TINVEST_ACCOUNT_IDS=account_id_1,account_id_2
```

Также поддерживаются имена `TINVEST_TOKEN` и `TINKOFF_INVEST_API_TOKEN`.
Для Execution можно задать человекочитаемые имена счетов:
`EXECUTION_TINVEST_ACCOUNTS=account_id_1:Main,account_id_2:IIS`.

Запуск всей системы одной командой:

```bash
docker compose up --build
```

После запуска:

- UI данных: http://localhost:8080/data/
- API данных: http://localhost:8080/api/data/
- UI стратегий: http://localhost:8080/strategies/
- API стратегий: http://localhost:8080/api/strategies/
- UI Execution: http://localhost:8080/execution/
- API Execution: http://localhost:8080/api/execution/
- Auth UI: http://localhost:8080/tech/auth/
- Auth API: http://localhost:8080/api/tech/
- Swagger backend: http://localhost:8080/api/data/docs

## Метрики и мониторинг

Observability-стек запускается через отдельный Docker Compose profile:

```bash
docker compose --profile observability up --build
```

После запуска доступны:

- Grafana через gateway: http://localhost:8080/grafana/
- OpenSearch API через gateway: http://localhost:8080/opensearch-api/
- OpenSearch Dashboards: http://localhost:5601/app/home
- GlitchTip: http://localhost:8001/

OpenSearch настраивается автоматически контейнером `opensearch-bootstrap`: создается ISM policy `technical-logs-retention`, index template `its-app-logs`, сегодняшний индекс `its-app-logs-YYYY.MM.DD`, index pattern `its-app-logs-*` в OpenSearch Dashboards и default index pattern. Ручная настройка в OpenSearch Dashboards не требуется.

GlitchTip использует отдельную БД `glitchtip-postgres`. Миграции и bootstrap admin выполняются автоматически контейнером `glitchtip-migrate`.
Логин GlitchTip по умолчанию: `admin@example.com`, пароль: `admin123`.
Также автоматически создаются организация `ITS`, команда `platform`, проект `its-platform` и default project key.
Их можно переопределить:

```bash
GLITCHTIP_ADMIN_EMAIL=admin@example.com GLITCHTIP_ADMIN_PASSWORD=change_me GLITCHTIP_BOOTSTRAP_ORGANIZATION=ITS GLITCHTIP_BOOTSTRAP_PROJECT=its-platform docker compose --profile observability up --build
```

В Grafana по умолчанию создается datasource Prometheus и dashboard `ITS Platform Overview`.
Логин Grafana по умолчанию: `admin`, пароль: `admin`.
Их можно переопределить:

```bash
GRAFANA_ADMIN_USER=admin GRAFANA_ADMIN_PASSWORD=change_me docker compose --profile observability up --build
```

Backend-сервисы отдают Prometheus metrics на `/metrics` внутри Docker-сети:

- `http://data-backend:8000/metrics`
- `http://strategy-backend:8000/metrics`
- `http://ga-backend:8000/metrics`
- `http://execution-backend:8000/metrics`
- `http://tech-system-backend:8000/metrics`
- `http://event-log-backend:8000/metrics`

Prometheus собирает эти endpoints автоматически. Для локальной ручной проверки можно выполнить запрос из контейнера:

```bash
docker compose exec data-backend curl -s http://localhost:8000/metrics
```

Observability в backend-приложениях настраивается через env:

```dotenv
OBSERVABILITY_ENABLED=true
OBSERVABILITY_METRICS_ENABLED=true
OBSERVABILITY_JSON_LOGS_ENABLED=true
OBSERVABILITY_TRACING_ENABLED=false
OBSERVABILITY_ERRORS_ENABLED=true
SENTRY_DSN=http://85dc29c1a9b645aaab8680880aea79db@glitchtip-web:8000/1
SENTRY_TRACES_SAMPLE_RATE=0.01
```

Чтобы полностью выключить observability middleware:

```bash
OBSERVABILITY_ENABLED=false docker compose up --build
```

Порт gateway можно переопределить:

```bash
ITS_GATEWAY_PORT=8090 docker compose up --build
```

## Сервисы

- `data-backend` - Python, FastAPI, asyncio. Отдает инструменты и свечи из Tinkoff Invest.
- `data-ui` - Vue 3 UI для визуализации рыночных данных, dark mode, RU/EN.
- `strategy-backend` - Python, FastAPI. Отдает registry компонентов и готовых стратегий.
- `strategy-ui` - Vue 3 UI для модельеров торговых стратегий, dark mode, RU/EN.
- `execution-backend` - Python, FastAPI. Читает брокерские счета T-Invest и принимает stub-приказы.
- `execution-ui` - Vue 3 UI личного кабинета брокерских счетов.
- `tech-system-backend` - Python, FastAPI. Технические API платформы, включая auth/JWT.
- `tech-system-ui` - Vue 3 UI для входа и регистрации.
- `nginx-gateway` - единая точка входа, маршрутизирует `/data/` в UI и `/api/data/` в backend.

## Структура

```text
services/data_backend/   # backend сервиса данных
services/strategy_backend/ # backend registry торговых стратегий
ui/data-ui/              # Vue UI сервиса данных
ui/strategy-ui/          # Vue UI сервиса торговых стратегий
ui/execution-ui/         # Vue UI исполнительной подсистемы
ui/tech-system-ui/       # Vue UI технической подсистемы
its/execution/           # логика Execution и адаптер T-Invest
infra/nginx/             # gateway nginx
docker-compose.yml       # общая оркестрация
```


Генерация pdf документации
```bash
poetry run python scripts/build_docs_pdf.py
```
