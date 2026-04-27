# ISSAT

Intelligent system for securities analysis and trading.

## Быстрый старт

Создай или обнови `.env` в корне проекта:

```dotenv
tinvest_token=your_tinkoff_invest_token
```

Также поддерживаются имена `TINVEST_TOKEN` и `TINKOFF_INVEST_API_TOKEN`.

Запуск всей системы одной командой:

```bash
docker compose up --build
```

После запуска:

- UI данных: http://localhost:8080/data/
- API данных: http://localhost:8080/api/data/
- Swagger backend: http://localhost:8080/api/data/docs

Порт gateway можно переопределить:

```bash
ITS_GATEWAY_PORT=8090 docker compose up --build
```

## Сервисы

- `data-backend` - Python, FastAPI, asyncio. Отдает инструменты и свечи из Tinkoff Invest.
- `data-ui` - Vue 3 UI для визуализации рыночных данных, dark mode, RU/EN.
- `nginx-gateway` - единая точка входа, маршрутизирует `/data/` в UI и `/api/data/` в backend.

## Структура

```text
services/data_backend/   # backend сервиса данных
ui/data-ui/              # Vue UI сервиса данных
infra/nginx/             # gateway nginx
docker-compose.yml       # общая оркестрация
```
