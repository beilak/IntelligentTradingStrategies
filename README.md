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
