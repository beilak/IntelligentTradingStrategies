# API и интеграции

[К оглавлению](README.md)

Все внешние запросы проходят через `nginx-gateway`. Ниже указаны публичные пути, доступные после запуска на `localhost:8080`.

## Swagger

| API | URL |
| --- | --- |
| Data Backend | `/api/data/docs` |
| Strategy Backend | `/api/strategies/docs` |
| GA Backend | `/api/ga/docs` |

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

## Интеграционные зависимости

Strategy Backend и GA Backend не обращаются к T-Invest напрямую. Они получают данные через Data Backend. Это снижает связанность и позволяет заменить источник данных без переписывания тестов и GA.

