# API и интеграции

[К оглавлению](README.md)

Все внешние запросы проходят через `nginx-gateway`. Ниже указаны публичные пути, доступные после запуска на `localhost:8080`.

## Swagger

| API | URL |
| --- | --- |
| Data Backend | `/api/data/docs` |
| Strategy Backend | `/api/strategies/docs` |
| GA Backend | `/api/ga/docs` |
| Execution Backend | `/api/execution/docs` |
| Tech System Backend | `/api/tech/docs` |
| Event Log Backend | `/api/event-log/docs` |

Большинство бизнес-endpoints требуют JWT Bearer token, полученный через Tech System (`POST /api/tech/auth/login` или `POST /api/tech/auth/register`). Health-check endpoints доступны без бизнес-параметров.

## Data API

Базовый путь:

```text
/api/data/
```

### Health

```http
GET /api/data/health
```

Ответ:

```json
{"status":"ok"}
```

### Источники

```http
GET /api/data/sources
```

Возвращает список подключенных источников и доступных ресурсов.

### Акции

```http
GET /api/data/stocks
```

Основные параметры:

| Параметр | Описание |
| --- | --- |
| `class_code` | класс инструментов, по умолчанию `TQBR` |
| `search` | поиск по тикеру или названию |
| `tickers` | список тикеров |
| `exchange` | фильтр биржи |
| `sector` | фильтр сектора |
| `country_of_risk` | страна риска |
| `limit`, `offset` | пагинация |

### Валюты

```http
GET /api/data/currencies
```

Возвращает валютные инструменты.

### Универсальный справочник инструментов

```http
GET /api/data/instruments
```

Поддерживает поиск и фильтрацию по `instrument_types`, `class_code`, `exchange`, `currency`, `api_trade_available`, `limit`, `offset`.

### Цены

```http
GET /api/data/prices
```

Основные параметры:

| Параметр | Описание |
| --- | --- |
| `figis` | список FIGI |
| `tickers` | список тикеров |
| `class_code` | класс инструментов |
| `instrument_type` | `stocks` или `currencies` |
| `start_date` | дата начала |
| `end_date` | дата окончания |
| `interval` | интервал свечей |
| `is_complete` | только завершенные свечи |

### Custom gold bars

```http
GET /api/data/custom-gold-bars
```

Дополнительные параметры:

| Параметр | Описание |
| --- | --- |
| `gold_ticker` | тикер золота, по умолчанию `GLDRUB_TOM` |
| `gold_class_code` | класс золота, по умолчанию `CETS` |
| `count` | количество золотых единиц |
| `bar_type` | тип золотого бара |

### Дивиденды

```http
GET /api/data/dividends
```

Параметры:

- `figis`;
- `tickers`;
- `class_code`;
- `start_date`;
- `end_date`.

### Monte Carlo и RSS

```http
GET  /api/data/monte-carlo
GET  /api/data/rss
GET  /api/data/rss/sources
POST /api/data/rss/load
```

`monte-carlo` строит сценарии цены закрытия для одного инструмента. RSS endpoints читают, фильтруют и загружают новости из настроенных источников.

## Strategy API

Базовый путь:

```text
/api/strategies/
```

### Health

```http
GET /api/strategies/health
```

### Реестр

```http
GET /api/strategies/registry
```

Возвращает группы:

- `pre_selection`;
- `signal_model`;
- `allocation`;
- `strategy_model`;
- `trading_strategy_model`.

### Модели ядра

```http
GET /api/strategies/models
GET /api/strategies/models/{model_name}
```

Детальный endpoint возвращает:

- описание модели;
- состав pipeline;
- component groups;
- доступные отчеты.

### Полные торговые стратегии

```http
GET /api/strategies/trading-strategies
GET /api/strategies/trading-strategies/{strategy_name}
```

### Production state торговых стратегий

```http
GET /api/strategies/trading-strategies/prod-ready
PUT /api/strategies/trading-strategies/{strategy_name}/prod-ready
GET /api/strategies/strategy-type
```

Эти endpoints отмечают trading strategy как готовую к Execution, возвращают список таких стратегий и описывают тип полноценной стратегии.

### CPCV

```http
GET  /api/strategies/models/{model_name}/cpcv/tests
GET  /api/strategies/models/{model_name}/cpcv/tests/{test_name}
POST /api/strategies/models/{model_name}/cpcv/run
```

Тело `POST`:

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

Тело `POST`:

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

Тело `POST`:

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

### Backtesting для full trading strategy

```http
GET  /api/strategies/trading-strategies/{strategy_name}/backtest/tests
GET  /api/strategies/trading-strategies/{strategy_name}/backtest/tests/{test_name}
POST /api/strategies/trading-strategies/{strategy_name}/backtest/run
```

### Сравнение

```http
GET /api/strategies/comparison/latest
```

## GA API

Базовый путь:

```text
/api/ga/
```

### Health

```http
GET /api/ga/health
```

### Алфавиты

```http
GET /api/ga/alphabets
```

Возвращает группы генов и размер пространства поиска.

### Список запусков

```http
GET /api/ga/runs
```

### Детали запуска

```http
GET /api/ga/runs/{run_id}
```

### Запуск GA

```http
POST /api/ga/runs
```

Пример тела:

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

Базовый путь:

```text
/api/execution/
```

### Health

```http
GET /api/execution/health
```

Ответ содержит брокера, наличие токена, число настроенных счетов и `order_submission_mode`.

### Счета и обзор

```http
GET /api/execution/accounts
GET /api/execution/accounts/{account_id}/overview?operations_days=30
```

Возвращает настроенные счета T-Invest, портфель, позиции, лимиты вывода, маржинальные атрибуты, активные заявки, stop-заявки и операции.

### Заявки

```http
POST /api/execution/accounts/{account_id}/orders
POST /api/execution/accounts/{account_id}/stop-orders
```

Обычная заявка содержит `instrument_id`, `side`, `order_type`, `quantity`, `price`, `time_in_force` и комментарий. Stop-заявка содержит `stop_order_type`, `stop_price`, optional `limit_price` и `expire_at`. В режиме `stub` заявка валидируется локально и не отправляется брокеру.

### Рыночные данные и стратегии

```http
GET       /api/execution/market-data/last-price?instrument_id=...
WebSocket /api/execution/ws/orderbook
GET       /api/execution/accounts/{account_id}/strategies
PUT       /api/execution/accounts/{account_id}/strategies/{strategy_name}
DELETE    /api/execution/accounts/{account_id}/strategies/{strategy_name}
POST      /api/execution/accounts/{account_id}/strategies/{strategy_name}/runs
```

Назначение стратегии сохраняется в БД. Запуск использует параметры периода, интервала, `order_type`, `limit_offset_pct` и `min_order_value`.

## Tech System API

Базовый путь:

```text
/api/tech/
```

Основные группы:

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

Tech System отвечает за регистрацию, JWT access/refresh tokens, роли, permissions, заявки на роли, блокировку пользователей и аудит auth/RBAC-событий.

## Event Log API

Базовый путь:

```text
/api/event-log/
```

```http
GET /api/event-log/health
GET /api/event-log/events
GET /api/event-log/events/filter-options
```

`events` поддерживает фильтры `id`, `date_time_from`, `date_time_to`, `service`, `user`, `http_action`, `ip_address`, `path`, `header`, `body`, `limit`, `offset`.

## Интеграционные зависимости

Strategy Backend, GA Backend и Execution Backend используют Data Backend для рыночных данных. Execution Backend также обращается к T-Invest broker API для счетов и заявок. Все backend-сервисы устанавливают Event Log и Observability middleware, а защищенные endpoints используют JWT/RBAC из Tech System.
