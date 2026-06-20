# Эксплуатация, конфигурация и передача системы

[К оглавлению](README.md)

## Состав поставки

Минимальная поставка системы включает:

- исходный код репозитория;
- `docker-compose.yml`;
- Dockerfile для каждого сервиса;
- frontend-приложения;
- backend-сервисы;
- Python-ядро стратегий;
- GA-движок;
- Execution-модуль;
- Tech System с RBAC/JWT;
- Event Log и observability-конфигурацию;
- Markdown-документацию в `docs`;
- PDF-версии документации в `docs/pdf`;
- скриншоты интерфейсов в `docs/img`;
- тесты в `tests`.

## Основная команда запуска

```bash
docker compose up --build
```

Команда является основной точкой входа для пользователя и заказчика.

## PDF-версия документации

Markdown-файлы в `docs` являются основным редактируемым источником документации. Для передачи документации единым файлом система содержит готовые PDF-версии:

- `docs/pdf/its_documentation_ru.pdf`;
- `docs/pdf/its_documentation_en.pdf`.

В web-интерфейсе документации кнопка `PDF` скачивает файл на текущем языке интерфейса. После изменения Markdown-документации PDF можно пересобрать командой:

```bash
poetry run python scripts/build_docs_pdf.py
```

Скрипт использует Markdown-файлы и изображения из `docs/img`, формирует русскую и английскую версии PDF и сохраняет результат в `docs/pdf`.

## Переменные окружения

| Переменная | Назначение | Значение по умолчанию |
| --- | --- | --- |
| `tinvest_token` | токен T-Invest | пусто |
| `TINVEST_TOKEN` | альтернативное имя токена | пусто |
| `TINKOFF_INVEST_API_TOKEN` | альтернативное имя токена | пусто |
| `EXECUTION_TINVEST_TOKEN` | отдельный токен T-Invest для Execution | пусто |
| `EXECUTION_TINVEST_ACCOUNT_IDS` | список счетов Execution через запятую | пусто |
| `EXECUTION_TINVEST_ACCOUNTS` | список счетов с именами, например `id:Main` | пусто |
| `EXECUTION_ORDER_SUBMISSION_MODE` | режим заявок: `real` или `stub` | `real` |
| `DATA_BACKEND_STOCKS_TTL_MINUTES` | TTL справочника инструментов | `30` |
| `DATA_BACKEND_BASE_URL` | адрес Data Backend для внутренних сервисов | задается в compose |
| `STRATEGY_TEST_CACHE_DIR` | кэш CPCV | `/app/its/data/strategy_tests/cpcv` |
| `STRATEGY_WF_CACHE_DIR` | кэш WalkForward | `/app/its/data/strategy_tests/walk_forward` |
| `STRATEGY_BACKTEST_CACHE_DIR` | кэш Backtesting | `/app/its/data/strategy_tests/backtest` |
| `GA_RUN_CACHE_DIR` | кэш GA-запусков | `/app/its/data/ga_runs` |
| `GA_MODELS_DIR` | директория материализации стратегий | `/app/its/strategies/models` |
| `AUTH_JWT_SECRET_KEY` | секрет JWT для Tech System и защищенных API | dev-secret в compose |
| `AUTH_ACCESS_TOKEN_TTL_MINUTES` | время жизни access token | `30` |
| `AUTH_REFRESH_TOKEN_TTL_DAYS` | время жизни refresh token | `7` |
| `EVENT_LOG_DATABASE_URL` | БД журнала событий | задается в compose |
| `OBSERVABILITY_ENABLED` | общий флаг observability middleware | `true` |
| `OBSERVABILITY_TRACING_ENABLED` | трассировка через OTEL | `false` |
| `SENTRY_DSN` | DSN GlitchTip/Sentry | задается в compose |
| `ITS_GATEWAY_PORT` | внешний порт gateway | `8080` |

## Хранение данных

В Docker Compose используются volumes:

```text
t-invest-cache
strategy-test-cache
ga-cache
postgres-data
event-log-postgres-data
prometheus-data
grafana-data
opensearch-data
```

Назначение:

- не терять загруженные данные при перезапуске контейнеров;
- не повторять дорогие обращения к источникам;
- сохранять тесты между сессиями;
- сохранять историю GA-запусков;
- хранить пользователей, роли, назначения стратегий и журнал событий;
- хранить состояние observability-инструментов.

## Материализованные стратегии

GA Backend монтирует:

```text
./its/strategies/models:/app/its/strategies/models
```

Это значит, что TOP стратегии, созданные GA, появляются в рабочей копии проекта как обычные Python-файлы.

После генерации рекомендуется:

1. Просмотреть созданный файл.
2. Проверить импорт в `its/strategies/models/__init__.py`.
3. Запустить Strategy Lab и убедиться, что модель появилась в реестре.
4. Провести CPCV, WalkForward и Backtesting.
5. При необходимости зафиксировать изменения в системе контроля версий.

## Логи

Логи можно смотреть стандартными средствами Docker:

```bash
docker compose logs -f
docker compose logs -f data-backend
docker compose logs -f strategy-backend
docker compose logs -f ga-backend
docker compose logs -f execution-backend
docker compose logs -f tech-system-backend
docker compose logs -f event-log-backend
```

## Observability-профиль

Для запуска мониторинга:

```bash
docker compose --profile observability up --build
```

После запуска доступны:

- Grafana: `http://localhost:8080/grafana/`;
- OpenSearch API: `http://localhost:8080/opensearch-api/`;
- OpenSearch Dashboards: `http://localhost:5601/app/home`;
- GlitchTip: `http://localhost:8001/`.

Backend-сервисы публикуют `/metrics`, пишут структурные JSON-логи и отправляют ошибки в GlitchTip, если включены соответствующие env-переменные.

## Обновление системы

Рекомендуемый порядок:

1. Остановить контейнеры.
2. Получить новую версию кода.
3. Проверить `.env`.
4. Запустить:

```bash
docker compose up --build
```

5. Проверить `/health` и UI.

## Резервное копирование

Для сохранения результатов работы нужно учитывать:

- `its/strategies/models` - сгенерированные стратегии;
- Docker volume `strategy-test-cache` - сохраненные тесты;
- Docker volume `ga-cache` - GA-запуски;
- Docker volume `t-invest-cache` - кэш данных;
- Docker volume `postgres-data` - пользователи, роли и назначения стратегий;
- Docker volume `event-log-postgres-data` - журнал событий;
- observability volumes - метрики, dashboards и индексы логов;
- `.env` - локальные секреты, не передавать публично.

## Безопасность

Текущая конфигурация ориентирована на локальный или закрытый исследовательский контур.

Важно:

- не публиковать T-Invest токен;
- не публиковать `AUTH_JWT_SECRET_KEY`;
- не коммитить `.env`;
- не открывать gateway в публичный интернет без дополнительной аутентификации;
- использовать `EXECUTION_ORDER_SUBMISSION_MODE=stub` для демонстраций и проверок без реальных заявок;
- проверять список счетов `EXECUTION_TINVEST_ACCOUNT_IDS` перед включением `real` режима;
- учитывать, что CORS в backend разрешен широко для удобства разработки;
- ограничить доступ к серверу, если система запускается на удаленной машине.

## Ограничения текущей версии

Текущая версия:

- не является полноценным брокерским терминалом с промышленным риск-менеджментом;
- может отправлять заявки через Execution в `real` режиме, но не заменяет independent risk checks;
- поддерживает `stub` режим для безопасной проверки заявок без отправки брокеру;
- не гарантирует будущую доходность;
- зависит от доступности и качества внешнего источника данных.

Перед production-использованием нужно отдельно настроить лимиты риска, права пользователей, регламент подтверждения заявок и monitoring/alerting.

## Передача покупателю

При передаче системы рекомендуется предоставить:

- репозиторий или архив кода;
- инструкцию запуска;
- этот комплект документации;
- описание необходимых токенов и прав доступа;
- описание настроенных Execution-счетов и режима заявок;
- перечень известных ограничений;
- примеры тестовых запусков;
- список сгенерированных и базовых стратегий;
- результаты демонстрационных CPCV, WalkForward и Backtesting тестов.

## Проверка после передачи

Контрольный сценарий:

1. Создать `.env` с токеном.
2. Выполнить `docker compose up --build`.
3. Открыть Launchpad.
4. Перейти в Data Hub и загрузить котировки `SBER`.
5. Перейти в Strategy Lab и открыть базовую модель.
6. Запустить короткий Backtesting.
7. Перейти в GA Lab и открыть список алфавитов.
8. Запустить небольшой GA-поиск на малом числе поколений.
9. Убедиться, что TOP стратегия создана в `its/strategies/models`.
10. Перейти в Tech System, зарегистрироваться или войти.
11. Перейти в Execution и проверить список настроенных счетов.
12. В `stub` режиме создать тестовую заявку и убедиться, что она не отправлена брокеру.
