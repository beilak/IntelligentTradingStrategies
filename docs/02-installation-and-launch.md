# Установка, предварительные требования и запуск

[К оглавлению](README.md)

## Минимальные требования

Для обычного запуска системы пользователю достаточно:

- Docker Engine или Docker Desktop;
- Docker Compose v2;
- Git для получения исходного кода;
- доступ к интернету для сборки образов и обращения к источнику данных;
- токен T-Invest API для загрузки рыночных данных;
- идентификаторы брокерских счетов T-Invest для Execution, если нужен контур исполнения;
- свободный порт `8080` или другой порт, заданный через `ITS_GATEWAY_PORT`.

Рекомендуемые ресурсы рабочей станции:

- 4 CPU и выше;
- 8 GB RAM и выше;
- 5 GB свободного места для образов, кэшей данных и результатов тестов.

## Технологические требования для разработки

Если система запускается не только через Docker, а также дорабатывается локально, потребуются:

- Python `3.12.x`;
- Poetry;
- Node.js `20+`;
- npm;
- современный браузер.

Основные backend-библиотеки:

- FastAPI и Uvicorn для API-сервисов;
- pandas и NumPy для подготовки данных;
- scikit-learn pipeline-интерфейс для компонентов;
- skfolio для портфельной оптимизации и model selection;
- vectorbt для backtesting;
- PyGAD для генетического алгоритма;
- httpx, aiohttp, aiometer, async-lru для HTTP и асинхронной загрузки;
- t-tech-investments для интеграции с T-Invest.

Основные frontend-библиотеки:

- Vue 3;
- Vite;
- TypeScript;
- lucide-vue-next;
- ECharts в Data UI.

## Настройка токена

В корне проекта создать или обновить файл `.env`:

```dotenv
tinvest_token=your_tinkoff_invest_token
```

Также поддерживаются переменные:

```dotenv
TINVEST_TOKEN=your_tinkoff_invest_token
TINKOFF_INVEST_API_TOKEN=your_tinkoff_invest_token
```

Токен нужен Data Backend для получения инструментов, котировок, валют и дивидендов через T-Invest API. Execution использует `EXECUTION_TINVEST_TOKEN`, если он задан, иначе те же переменные токена.

Для Execution можно задать список счетов:

```dotenv
EXECUTION_TINVEST_ACCOUNT_IDS=account_id_1,account_id_2
EXECUTION_TINVEST_ACCOUNTS=account_id_1:Main,account_id_2:IIS
EXECUTION_ORDER_SUBMISSION_MODE=stub
```

`EXECUTION_ORDER_SUBMISSION_MODE=stub` проверяет заявки локально и не отправляет их брокеру. Значение по умолчанию - `real`.

## Запуск всей системы

Из корня проекта:

```bash
docker compose up --build
```

Команда собирает и запускает:

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
- PostgreSQL для прикладных данных и отдельный PostgreSQL для журнала событий;
- `nginx-gateway`.

## URL после запуска

| Компонент | URL |
| --- | --- |
| Главное окно | [http://localhost:8080/launchpad/](http://localhost:8080/launchpad/) |
| Data Hub | [http://localhost:8080/data/](http://localhost:8080/data/) |
| Strategy Lab | [http://localhost:8080/strategies/](http://localhost:8080/strategies/) |
| GA Lab | [http://localhost:8080/ga/](http://localhost:8080/ga/) |
| Execution | [http://localhost:8080/execution/](http://localhost:8080/execution/) |
| Tech System / Auth | [http://localhost:8080/tech/auth/](http://localhost:8080/tech/auth/) |
| Документация | [http://localhost:8080/docs/](http://localhost:8080/docs/) |
| Data API Swagger | [http://localhost:8080/api/data/docs](http://localhost:8080/api/data/docs) |
| Strategy API Swagger | [http://localhost:8080/api/strategies/docs](http://localhost:8080/api/strategies/docs) |
| GA API Swagger | [http://localhost:8080/api/ga/docs](http://localhost:8080/api/ga/docs) |
| Execution API Swagger | [http://localhost:8080/api/execution/docs](http://localhost:8080/api/execution/docs) |
| Tech API Swagger | [http://localhost:8080/api/tech/docs](http://localhost:8080/api/tech/docs) |
| Event Log API Swagger | [http://localhost:8080/api/event-log/docs](http://localhost:8080/api/event-log/docs) |

Если порт `8080` занят:

```bash
ITS_GATEWAY_PORT=8090 docker compose up --build
```

Тогда главное окно будет доступно по адресу:

```text
http://localhost:8090/launchpad/
```

## Проверка работоспособности

После старта открыть:

```text
http://localhost:8080/health
```

Ожидаемый ответ:

```text
ok
```

Также можно проверить API:

```text
http://localhost:8080/api/data/health
http://localhost:8080/api/strategies/health
http://localhost:8080/api/ga/health
http://localhost:8080/api/execution/health
http://localhost:8080/api/tech/health
http://localhost:8080/api/event-log/health
```

Ожидаемый JSON:

```json
{"status":"ok"}
```

## Данные и кэши

Docker Compose создает именованные volumes:

| Volume | Назначение |
| --- | --- |
| `t-invest-cache` | кэш котировок, справочников и дивидендов |
| `strategy-test-cache` | сохраненные CPCV, WalkForward и Backtesting отчеты |
| `ga-cache` | сохраненные GA-запуски |
| `postgres-data` | пользователи, роли, назначения стратегий и прикладное состояние |
| `event-log-postgres-data` | журнал событий пользовательских и API-действий |

GA также записывает материализованные стратегии в локальную папку:

```text
its/strategies/models
```

## Типовые проблемы запуска

### Не задан T-Invest токен

Data Backend вернет ошибку `503` с сообщением о необходимости задать `tinvest_token`, `TINVEST_TOKEN` или `TINKOFF_INVEST_API_TOKEN`.

Решение: проверить `.env` в корне проекта и перезапустить контейнеры.

### Порт 8080 занят

Решение:

```bash
ITS_GATEWAY_PORT=8090 docker compose up --build
```

### Нет котировок для выбранного периода

Причины:

- инструмент не найден;
- выбран слишком ранний период;
- источник данных не вернул свечи;
- неверный `class_code` или тип инструмента.

Решение: проверить тикер, FIGI, `class_code`, интервал и даты в Data Hub.

### Слишком долгий GA-запуск

Причины:

- большая популяция;
- много поколений;
- длинный период данных;
- большое количество активов;
- сложные CPCV и WalkForward параметры.

Решение: уменьшить `num_generations`, `sol_per_pop`, число активов или длину периода.

### Execution не показывает счета

Причины:

- не задан токен T-Invest;
- не задан `EXECUTION_TINVEST_ACCOUNT_IDS` или `EXECUTION_TINVEST_ACCOUNTS`;
- указанный счет не возвращается T-Invest API для текущего токена.

Решение: проверить `.env`, права токена и перезапустить контейнеры.
