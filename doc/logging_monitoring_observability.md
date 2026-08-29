# Логирование, мониторинг и observability в ITS

Документ фиксирует текущую реализацию логирования, мониторинга и observability, которая уже есть в проекте. Это не целевая архитектура "когда-нибудь", а описание фактических модулей, сервисов, таблиц, настроек, UI и ограничений в текущем коде.

## 1. Общая схема

В проекте сейчас есть несколько независимых слоев наблюдаемости:

| Слой | Назначение | Где реализован |
|---|---|---|
| Audit event log | Append-only журнал действий пользователя и HTTP-запросов | `its/event_log`, `services/event_log_backend`, `event-log-postgres`, Tech System UI |
| Application JSON logs | Технические логи приложений в stdout с request/trace context | `its/observability/logging.py` |
| Operational log search | Сбор Docker logs через Fluent Bit и индексация в OpenSearch | `infra/observability/fluent-bit`, `infra/observability/opensearch` |
| Metrics | HTTP/audit метрики FastAPI + exporter-метрики БД и контейнеров | `its/observability/metrics.py`, Prometheus, Grafana |
| Error tracking | Sentry-compatible отправка backend exceptions в GlitchTip | `its/observability/tracing.py`, GlitchTip compose services |
| Tracing | Optional OpenTelemetry FastAPI instrumentation | `its/observability/tracing.py`, OTel Collector |

Audit event log не заменен OpenSearch. PostgreSQL audit log остается источником истины для действий пользователей. OpenSearch используется для технических application logs и расследований по runtime-поведению.

## 2. Запуск через Docker Compose

Базовая платформа:

```bash
docker compose up --build
```

Платформа вместе с observability stack:

```bash
docker compose --profile observability up --build
```

Все observability-сервисы описаны в `docker-compose.yml` и запускаются через profile `observability`. Backend-сервисы получают настройки observability через общий YAML anchor `x-observability-environment`.

Локальные URL по умолчанию:

| Сервис | URL |
|---|---|
| Grafana через gateway | `http://localhost:8080/grafana/` |
| Grafana direct port | `http://localhost:3000` |
| OpenSearch API через gateway | `http://localhost:8080/opensearch-api/` |
| OpenSearch API direct port | `http://localhost:9200` |
| OpenSearch Dashboards | `http://localhost:5601/app/home` |
| GlitchTip | `http://localhost:8001/` |

В `infra/nginx/nginx.conf`:

- `/api/event-log/` проксирует в `event-log-backend/api/v1/`;
- `/grafana/` проксирует в Grafana с `GF_SERVER_SERVE_FROM_SUB_PATH=true`;
- `/opensearch-api/` проксирует в OpenSearch;
- `/opensearch-dashboards` редиректит на direct port `:5601`;
- `/glitchtip` редиректит на direct port `:8001`.

Редиректы для OpenSearch Dashboards и GlitchTip сделаны потому, что эти UI некорректно работают под gateway subpath без дополнительной глубокой настройки base path/static/API routes.

## 3. Audit Event Log

### 3.1. Назначение

Audit event log фиксирует все HTTP-действия пользователя во всех FastAPI backend-сервисах. Принцип хранения - append only: новые события можно только добавлять, существующие записи нельзя обновлять или удалять.

### 3.2. Модуль

Основной код находится в `its/event_log`:

| Файл | Роль |
|---|---|
| `config.py` | Pydantic settings для БД event log и лимита body |
| `models.py` | SQLAlchemy модель таблицы `event_logs` |
| `middleware.py` | ASGI middleware, которое перехватывает HTTP request и пишет event |
| `repository.py` | Append, выборка, фильтры, сортировка и audit metrics |
| `storage.py` | Engine/session factory, создание схемы, append-only triggers |
| `router.py` | API чтения event logs и filter options |
| `schemas.py` | Response schemas и список колонок UI/API |
| `security.py` | Проверка доступа к просмотру event logs |
| `integration.py` | `install_event_log(app, service_name=...)` |

Отдельный backend для чтения логов находится в `services/event_log_backend/app/main.py`.

### 3.3. Подключение во все FastAPI

Event log middleware подключено в backend-сервисах через:

```python
install_event_log(app, service_name="...")
```

Текущие подключения:

| Сервис | `service_name` |
|---|---|
| `services/data_backend/app/main.py` | `data-backend` |
| `services/strategy_backend/app/main.py` | `strategy-backend` |
| `its/services/ga_backend/app/main.py` | `ga-backend` |
| `its/services/execution_backend/app/main.py` | `execution-backend` |
| `services/tech_system_backend/app/main.py` | `tech-system-backend` |
| `services/event_log_backend/app/main.py` | `event-log-backend` |

В `its/event_log/integration.py` используется `app.router.add_event_handler("startup", ensure_event_log_schema)`, потому что текущий объект FastAPI в проекте не поддерживал `app.add_event_handler`.

### 3.4. База данных

Audit logs хранятся в отдельной PostgreSQL БД:

| Compose service | Назначение |
|---|---|
| `event-log-postgres` | Отдельная PostgreSQL для audit log |
| `event-log-postgres-exporter` | Prometheus exporter для этой БД |
| `event-log-backend` | API для чтения audit log |

Compose defaults:

| Env | Значение по умолчанию |
|---|---|
| `EVENT_LOG_POSTGRES_DB` | `its_event_log` |
| `EVENT_LOG_POSTGRES_USER` | `its_event_log` |
| `EVENT_LOG_POSTGRES_PASSWORD` | `its_event_log_password` |
| `EVENT_LOG_POSTGRES_PORT` | `5433` |
| `EVENT_LOG_DATABASE_URL` | `postgresql+psycopg://its_event_log:its_event_log_password@event-log-postgres:5432/its_event_log` |

Локальный default в `its/event_log/config.py`:

```text
postgresql+psycopg://its_event_log:its_event_log_password@localhost:5433/its_event_log
```

### 3.5. Таблица `event_logs`

Модель определена в `its/event_log/models.py`.

| Колонка | Тип | Описание |
|---|---|---|
| `id` | `BIGINT IDENTITY PRIMARY KEY` | Идентификатор события |
| `date_time` | `TIMESTAMP WITH TIME ZONE` | UTC-время события, индекс |
| `service` | `VARCHAR(120)` | Имя backend-сервиса, индекс |
| `user` | `TEXT` | Email/sub из JWT или `unauth`, индекс |
| `http_action` | `VARCHAR(16)` | HTTP method: GET, POST, PUT и т.д., индекс |
| `ip_address` | `VARCHAR(128)` | IP клиента, индекс |
| `path` | `TEXT` | Path + query string |
| `header` | `JSONB` | Заголовки запроса после маскирования |
| `body` | `TEXT NULL` | Request body после маскирования и возможной обрезки |

Список колонок для API/UI зафиксирован в `EVENT_LOG_COLUMNS`:

```text
id, date_time, service, user, http_action, ip_address, path, header, body
```

### 3.6. Append-only гарантия

Append-only реализован на уровне БД в `its/event_log/storage.py`:

- `ensure_event_log_schema()` создает таблицу через SQLAlchemy metadata;
- `_ensure_event_log_columns()` добавляет `ip_address`, если его нет, и индекс `ix_event_logs_ip_address`;
- `_ensure_append_only_triggers()` создает PostgreSQL function `prevent_event_logs_mutation()`;
- триггеры `event_logs_prevent_update` и `event_logs_prevent_delete` запрещают `UPDATE` и `DELETE`.

Если кто-то попробует изменить или удалить запись напрямую в PostgreSQL, БД выбросит exception:

```text
event_logs is append-only: UPDATE/DELETE is not allowed
```

### 3.7. Что пишет middleware

`EventLogMiddleware` в `its/event_log/middleware.py`:

- работает только для ASGI scope `http`;
- перехватывает request body через `receive_wrapper`;
- ограничивает размер body через `EVENT_LOG_MAX_BODY_BYTES`, default `5 * 1024 * 1024`;
- после завершения запроса пишет event через `append_event_log`;
- запись выполняется через `asyncio.to_thread`, чтобы не блокировать event loop синхронным SQLAlchemy commit;
- если запись в audit DB упала, request пользователя не ломается, ошибка логируется и увеличиваются failure metrics.

Поля вычисляются так:

| Поле | Логика |
|---|---|
| `service` | Значение `service_name`, переданное в `install_event_log` |
| `user` | `email` или `sub` из JWT access token; иначе `unauth` |
| `http_action` | `scope["method"]` |
| `ip_address` | Первый IP из `X-Forwarded-For`, затем `X-Real-IP`, затем `scope["client"][0]`, затем `unknown` |
| `path` | `scope["path"]` + decoded query string |
| `header` | Все headers lower-case, после маскирования sensitive headers |
| `body` | Request body UTF-8, после маскирования sensitive body |

### 3.8. Маскирование чувствительных данных

В audit log сейчас реализованы два специальных правила:

1. Для `/auth/login` маскируется `password` в body.

Пример:

```json
{"email":"beylak@yandex.ru","password":"***"}
```

2. Bearer token в header `authorization` маскируется.

Пример:

```json
{"authorization":"Bearer ****"}
```

Если authorization не Bearer, значение сохраняется как есть. Это поведение покрыто тестом.

Дополнительно application JSON logs проходят через общий redaction helper `its/observability/redaction.py`, который маскирует ключи с частями:

```text
authorization, cookie, password, passwd, token, secret, api_key, apikey, client_secret, private_key
```

### 3.9. API event log backend

Router находится в `its/event_log/router.py`.

Endpoints:

| Method | Path | Описание |
|---|---|---|
| `GET` | `/api/event-log/events` | Список event logs с фильтрами, pagination и колонками |
| `GET` | `/api/event-log/events/filter-options` | Списки distinct `services` и `users` для dropdown-фильтров |

На уровне FastAPI router paths это `/events` и `/events/filter-options`; gateway добавляет `/api/event-log/`.

Доступ защищен через `require_event_log_access_token`. Для UI требуется permission `system.logs.read`.

Фильтры API:

| Query param | Логика |
|---|---|
| `id` | exact match |
| `date_time_from` | `date_time >= value` |
| `date_time_to` | `date_time <= value` |
| `service` | exact match |
| `user` | exact match |
| `http_action` | `ILIKE contains` |
| `ip_address` | `ILIKE contains` |
| `path` | `ILIKE contains` |
| `header` | `CAST(header AS TEXT) ILIKE contains` |
| `body` | `ILIKE contains` |
| `limit` | 1..500, default 100 |
| `offset` | default 0 |

Сортировка гарантирована в `its/event_log/repository.py`:

```sql
ORDER BY event_logs.date_time DESC, event_logs.id DESC
```

То есть в API и UI сверху приходят самые свежие события; `id DESC` используется как tie-breaker для одинакового `date_time`.

### 3.10. Event log metrics

В `append_event_log()` добавлены audit metrics:

| Metric | Тип | Labels |
|---|---|---|
| `its_audit_events_total` | counter | `service`, `method`, `result` |
| `its_audit_write_duration_seconds` | histogram | `service`, `result` |
| `its_audit_write_failures_total` | counter | `service`, `error_type` |

Эти метрики доступны на `/metrics` backend-сервисов и собираются Prometheus.

### 3.11. UI Event Logs

UI расположен в `ui/tech-system-ui`.

Ключевые файлы:

| Файл | Роль |
|---|---|
| `src/api.ts` | TypeScript types и API client для `/api/event-log` |
| `src/App.vue` | Экран Tech System, кнопка Event Logs, фильтры, таблица |
| `src/styles.css` | Стили full-screen Event Logs и карточек observability |

В Tech System есть отдельные модули:

- `Журнал событий` - audit event log;
- `Управление доступом`;
- `Настройки системы` - disabled placeholder;
- `Grafana` - external link;
- `OpenSearch` - external link;
- `GlitchTip` - external link.

Event Logs открывается отдельной кнопкой и занимает отдельный полноэкранный view внутри Tech System. Это оставляет место для будущих кнопок/подсистем.

UI фильтры соответствуют структуре БД:

| UI filter | Тип UI |
|---|---|
| `id` | input |
| `date_time_from` | календарь + время (`datetime-local`) |
| `date_time_to` | календарь + время (`datetime-local`) |
| `service` | dropdown из `/events/filter-options` |
| `user` | dropdown из `/events/filter-options` |
| `http_action` | dropdown GET/POST/PUT/PATCH/DELETE/OPTIONS |
| `ip_address` | search input |
| `path` | search input |
| `header` | search input |
| `body` | search input |

Таблица строится по `columns`, которые возвращает backend. Это снижает риск расхождения UI и backend schema.

## 4. Observability Python Module

### 4.1. Модуль

Код находится в `its/observability`:

| Файл | Роль |
|---|---|
| `config.py` | Pydantic settings |
| `integration.py` | `install_observability(app, service_name=...)` |
| `logging.py` | JSON logging formatter |
| `metrics.py` | In-memory Prometheus-compatible registry |
| `redaction.py` | Маскирование secrets в JSON logs |
| `request_context.py` | Context vars для request_id/service/trace/span |
| `tracing.py` | OpenTelemetry и GlitchTip/Sentry SDK hooks |

Все основные backend-сервисы вызывают:

```python
install_observability(app, service_name="...")
```

### 4.2. Pydantic settings

Настройки объявлены в `its/observability/config.py`.

| Env | Code default | Compose default | Описание |
|---|---:|---:|---|
| `OBSERVABILITY_ENABLED` | `true` | `true` | Главный выключатель observability middleware |
| `OBSERVABILITY_ENVIRONMENT` | `dev` | `dev` | Environment label |
| `OBSERVABILITY_RELEASE` | `1.0.0` | `1.0.0` | Версия/release |
| `OBSERVABILITY_JSON_LOGS_ENABLED` | `true` | `true` | Включает JSON formatter для root logger |
| `OBSERVABILITY_METRICS_ENABLED` | `true` | `true` | Включает `/metrics` |
| `OBSERVABILITY_METRICS_PATH` | `/metrics` | `/metrics` | Путь Prometheus metrics endpoint |
| `OBSERVABILITY_TRACING_ENABLED` | `false` | `false` | Включает OpenTelemetry instrumentation |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `None` | `http://otel-collector:4317` | OTLP endpoint |
| `OBSERVABILITY_ERRORS_ENABLED` | `false` | `true` | Включает GlitchTip/Sentry SDK при наличии DSN |
| `SENTRY_DSN` | `None` | `http://85dc29c1a9b645aaab8680880aea79db@glitchtip-web:8000/1` | GlitchTip/Sentry DSN внутри Docker network |
| `SENTRY_TRACES_SAMPLE_RATE` | `0.0` | `0.01` | Sampling для Sentry-compatible traces |

Важно: в коде `OBSERVABILITY_ERRORS_ENABLED` по умолчанию `false`, но в Docker Compose он переопределен в `true`, чтобы GlitchTip работал из коробки в compose stack.

### 4.3. Observability middleware

`ObservabilityMiddleware` в `its/observability/integration.py`:

- генерирует `x-request-id`, если request не передал его сам;
- возвращает `x-request-id` в response headers;
- читает W3C `traceparent` и кладет `trace_id`/`span_id` в context vars;
- считает HTTP request metrics;
- считает in-progress gauge;
- логирует unhandled exceptions;
- увеличивает exception counter;
- не применяется, если `OBSERVABILITY_ENABLED=false`.

### 4.4. JSON logs

`its/observability/logging.py` настраивает root logger на JSON output.

Каждая запись включает:

```text
timestamp, level, service, environment, version, logger, message,
request_id, trace_id, span_id, exception
```

Перед сериализацией payload проходит через `redact_mapping()`, чтобы не отправлять secrets в stdout, Fluent Bit и OpenSearch.

### 4.5. Metrics

В проекте реализован собственный in-memory Prometheus-compatible registry в `its/observability/metrics.py`. Он поддерживает counters, gauges и histograms и рендерит plain text в Prometheus exposition format.

HTTP metrics:

| Metric | Тип | Labels |
|---|---|---|
| `its_http_requests_total` | counter | `service`, `method`, `route`, `status_code`, `status_class` |
| `its_http_request_duration_seconds` | histogram | `service`, `method`, `route`, `status_code`, `status_class` |
| `its_http_requests_in_progress` | gauge | `service`, `method`, `route` |
| `its_http_exceptions_total` | counter | `service`, `route`, `exception_type` |

Audit metrics:

| Metric | Тип | Labels |
|---|---|---|
| `its_audit_events_total` | counter | `service`, `method`, `result` |
| `its_audit_write_duration_seconds` | histogram | `service`, `result` |
| `its_audit_write_failures_total` | counter | `service`, `error_type` |

Endpoint `/metrics` регистрируется только если включен `OBSERVABILITY_METRICS_ENABLED`.

### 4.6. Error tracking через GlitchTip/Sentry SDK

В `its/observability/tracing.py` реализован `configure_error_tracking()`:

- работает только если `OBSERVABILITY_ERRORS_ENABLED=true` и задан `SENTRY_DSN`;
- импортирует `sentry_sdk`;
- подключает `FastApiIntegration`, `SqlalchemyIntegration`, `LoggingIntegration(event_level="ERROR")`;
- задает `environment`, `release`, `traces_sample_rate`;
- ставит tag `service`;
- использует `send_default_pii=False`.

Зависимость установлена в `pyproject.toml`:

```toml
sentry-sdk = "^2.58.0"
```

### 4.7. Tracing через OpenTelemetry

В `configure_tracing()` есть optional FastAPI instrumentation:

- включается через `OBSERVABILITY_TRACING_ENABLED=true`;
- использует `FastAPIInstrumentor`;
- создает `TracerProvider` с resource `service.name`;
- если задан `OTEL_EXPORTER_OTLP_ENDPOINT`, добавляет `OTLPSpanExporter`;
- отправляет spans в OTel Collector.

Текущий compose default оставляет tracing выключенным. OTel Collector сейчас настроен на debug exporter, то есть это базовая приемка telemetry, а не полноценное production trace storage.

## 5. OpenSearch и Fluent Bit

### 5.1. Назначение

OpenSearch используется для технических operational logs:

- application JSON logs backend-сервисов;
- logs gateway/infra containers, если они попадают в Docker logs;
- расследования по `request_id`, `trace_id`, `service`, `level`, `message`.

Он не является append-only audit DB и не заменяет `event_logs`.

### 5.2. Compose services

| Service | Image | Назначение |
|---|---|---|
| `opensearch` | `opensearchproject/opensearch:2.18.0` | Search/index storage |
| `opensearch-dashboards` | `opensearchproject/opensearch-dashboards:2.18.0` | UI для поиска логов |
| `opensearch-bootstrap` | `curlimages/curl:8.11.1` | One-shot настройка policy/template/index pattern |
| `fluent-bit` | `fluent/fluent-bit:3.2.4` | Сбор Docker logs и отправка в OpenSearch |

OpenSearch запускается как single-node, security plugin отключен:

```yaml
discovery.type: single-node
DISABLE_SECURITY_PLUGIN: "true"
DISABLE_INSTALL_DEMO_CONFIG: "true"
```

### 5.3. Автоматический bootstrap OpenSearch

`infra/observability/opensearch/bootstrap.sh` делает без ручной настройки:

1. Ждет готовности OpenSearch.
2. Ждет готовности OpenSearch Dashboards.
3. Создает ISM policy `technical-logs-retention`.
4. Создает index template `its-app-logs`.
5. Создает сегодняшний индекс `its-app-logs-YYYY.MM.DD`.
6. Создает OpenSearch Dashboards index pattern `its-app-logs-*`.
7. Делает этот index pattern default.

Defaults:

| Env | Значение |
|---|---|
| `OPENSEARCH_LOG_INDEX_PREFIX` | `its-app-logs` |
| `OPENSEARCH_LOG_INDEX_PATTERN` | `its-app-logs-*` |
| `OPENSEARCH_LOG_INDEX_PATTERN_ID` | `its-app-logs` |
| `OPENSEARCH_LOG_TIME_FIELD` | `@timestamp` |

### 5.4. Index template

`infra/observability/opensearch/index-templates/its-app-logs.json`:

- index pattern: `its-app-logs-*`;
- shards: `1`;
- replicas: `0`;
- ISM policy: `technical-logs-retention`.

Mappings:

| Field | Type |
|---|---|
| `@timestamp` | `date` |
| `timestamp` | `date` |
| `level` | `keyword` |
| `service` | `keyword` |
| `environment` | `keyword` |
| `version` | `keyword` |
| `logger` | `keyword` |
| `message` | `text` |
| `request_id` | `keyword` |
| `trace_id` | `keyword` |
| `span_id` | `keyword` |
| `http_status_code` | `integer` |
| `duration_ms` | `float` |

### 5.5. Retention policy

`infra/observability/opensearch/ism-policies/technical-logs-retention.json`:

- default state: `hot`;
- transition to `delete` after `30d`;
- delete action removes old indices.

### 5.6. Fluent Bit pipeline

`infra/observability/fluent-bit/fluent-bit.conf`:

- tails `/var/lib/docker/containers/*/*.log`;
- parses Docker JSON logs через parser `docker`;
- пытается распарсить поле `log` как JSON через parser `its_json`;
- добавляет поле `environment`;
- отправляет в OpenSearch output;
- использует `Logstash_Format On`;
- prefix `its-app-logs`;
- HTTP server Fluent Bit включен на `:2020` для Prometheus scrape.

## 6. Prometheus, Grafana, Alertmanager

### 6.1. Prometheus

Compose service:

| Service | Image |
|---|---|
| `prometheus` | `prom/prometheus:v3.0.1` |

Config: `infra/observability/prometheus/prometheus.yml`.

Scrape jobs:

| Job | Targets |
|---|---|
| `prometheus` | `prometheus:9090` |
| `its-fastapi` | `data-backend:8000`, `strategy-backend:8000`, `ga-backend:8000`, `execution-backend:8000`, `tech-system-backend:8000`, `event-log-backend:8000` |
| `postgres` | `postgres-exporter:9187` |
| `event-log-postgres` | `event-log-postgres-exporter:9187` |
| `cadvisor` | `cadvisor:8080` |
| `fluent-bit` | `fluent-bit:2020` |
| `otel-collector` | `otel-collector:8888` |

Backend metrics path: `/metrics`.

### 6.2. Alert rules

Rules: `infra/observability/prometheus/alert_rules.yml`.

Текущие alerts:

| Alert | Условие |
|---|---|
| `ITSServiceDown` | `up{job="its-fastapi"} == 0` в течение 1 минуты |
| `ITSHighServerErrorRate` | Доля 5xx больше 2% за 5 минут |
| `ITSAuditLogWriteFailures` | Есть рост `its_audit_write_failures_total` за 5 минут |
| `ITSContainerRestarting` | Контейнер перезапускался больше 1 раза за 10 минут |

### 6.3. Alertmanager

Compose service:

| Service | Image |
|---|---|
| `alertmanager` | `prom/alertmanager:v0.27.0` |

Config: `infra/observability/alertmanager/alertmanager.yml`.

Сейчас настроен базовый receiver. Production-уведомления в email/Telegram/Slack/etc. не подключены.

### 6.4. Grafana

Compose service:

| Service | Image |
|---|---|
| `grafana` | `grafana/grafana-oss:11.4.0` |

Defaults:

| Env | Значение |
|---|---|
| `GRAFANA_ADMIN_USER` | `admin` |
| `GRAFANA_ADMIN_PASSWORD` | `admin` |
| `GRAFANA_ROOT_URL` | `http://localhost:8080/grafana/` |
| `GF_INSTALL_PLUGINS` | `grafana-opensearch-datasource` |

Provisioning:

- datasources: `infra/observability/grafana/provisioning/datasources/datasources.yml`;
- dashboards: `infra/observability/grafana/dashboards`.

Datasources:

| Name | Type | URL |
|---|---|---|
| `Prometheus` | `prometheus` | `http://prometheus:9090` |
| `OpenSearch` | `grafana-opensearch-datasource` | `http://opensearch:9200`, index `its-app-logs-*` |

Dashboard `ITS Platform Overview` содержит панели:

- `Request rate`;
- `5xx rate`;
- `HTTP p95 latency`;
- `Targets up`.

## 7. GlitchTip

### 7.1. Назначение

GlitchTip используется как open-source Sentry-compatible error tracking:

- группировка backend exceptions;
- issue lifecycle;
- stack traces;
- release/environment tags;
- Sentry DSN для backend-сервисов.

### 7.2. Compose services

| Service | Image | Назначение |
|---|---|---|
| `glitchtip-postgres` | `postgres:18-alpine` | Отдельная БД GlitchTip |
| `glitchtip-redis` | `valkey/valkey:8-alpine` | Redis/queue dependency |
| `glitchtip-migrate` | `glitchtip/glitchtip:latest` | One-shot migrations + bootstrap |
| `glitchtip-web` | `glitchtip/glitchtip:latest` | Web/API |
| `glitchtip-worker` | `glitchtip/glitchtip:latest` | Celery worker + beat |

GlitchTip имеет отдельную PostgreSQL БД и не использует ни основную ITS DB, ни audit event log DB.

### 7.3. Defaults

| Env | Значение |
|---|---|
| `GLITCHTIP_POSTGRES_DB` | `glitchtip` |
| `GLITCHTIP_POSTGRES_USER` | `glitchtip` |
| `GLITCHTIP_POSTGRES_PASSWORD` | `glitchtip_password` |
| `GLITCHTIP_SECRET_KEY` | `change-me-observability-secret` |
| `GLITCHTIP_DOMAIN` | `http://localhost:8001` |
| `GLITCHTIP_ADMIN_EMAIL` | `admin@example.com` |
| `GLITCHTIP_ADMIN_PASSWORD` | `admin123` |
| `GLITCHTIP_BOOTSTRAP_ORGANIZATION` | `ITS` |
| `GLITCHTIP_BOOTSTRAP_TEAM` | `platform` |
| `GLITCHTIP_BOOTSTRAP_PROJECT` | `its-platform` |
| `GLITCHTIP_PROJECT_PUBLIC_KEY` | `85dc29c1a9b645aaab8680880aea79db` |

Default login:

```text
admin@example.com / admin123
```

Для production эти значения надо переопределить через `.env`.

### 7.4. Bootstrap

`infra/observability/glitchtip/bootstrap.sh`:

1. Выполняет `./manage.py migrate --noinput`.
2. Создает или обновляет admin user.
3. Создает organization `ITS` со slug `its`.
4. Назначает admin владельцем organization.
5. Создает team `platform`.
6. Создает project `its-platform` с platform `python`.
7. Создает или обновляет default project key с public key из `GLITCHTIP_PROJECT_PUBLIC_KEY`.

`glitchtip-web` и `glitchtip-worker` зависят от успешного завершения `glitchtip-migrate`.

### 7.5. Backend SDK

Backend-сервисы отправляют ошибки в GlitchTip через `sentry-sdk`.

Compose default DSN:

```text
http://85dc29c1a9b645aaab8680880aea79db@glitchtip-web:8000/1
```

DSN указывает на internal Docker service `glitchtip-web:8000`, а не на localhost. Это правильно для backend containers.

## 8. OTel Collector

Compose service:

| Service | Image |
|---|---|
| `otel-collector` | `otel/opentelemetry-collector-contrib:0.115.1` |

Config: `infra/observability/otel-collector/config.yml`.

Receivers:

- OTLP gRPC `0.0.0.0:4317`;
- OTLP HTTP `0.0.0.0:4318`.

Pipelines:

- traces -> batch -> debug;
- metrics -> batch -> debug;
- logs -> batch -> debug.

Internal metrics endpoint: `0.0.0.0:8888`, Prometheus scrape job `otel-collector`.

Сейчас это техническая заготовка для OpenTelemetry. Долгосрочное trace-хранилище не подключено.

## 9. Tech System и Launchpad

Launchpad содержит плитку Tech System. Tech System сейчас является основной точкой входа для технических подсистем:

- Event Logs;
- Access Management;
- future System Settings;
- Grafana;
- OpenSearch;
- GlitchTip.

В Tech System внешние observability URL задаются через Vite env-переменные:

| Env | Назначение |
|---|---|
| `VITE_GRAFANA_URL` | Ссылка на Grafana |
| `VITE_OPENSEARCH_DASHBOARDS_URL` | Ссылка на OpenSearch Dashboards |
| `VITE_GLITCHTIP_URL` | Ссылка на GlitchTip |

В UI всех основных приложений добавлены кнопки возврата в launchpad в рамках предыдущих изменений, чтобы пользователь мог вернуться к главному экрану платформы.

## 10. Тесты

Текущие тесты по этой области:

| Файл | Что проверяет |
|---|---|
| `tests/event_log/test_middleware.py` | Маскирование password для `/auth/login`, маскирование Bearer token, извлечение IP |
| `tests/event_log/test_repository.py` | Сортировка event logs newest first |
| `tests/observability/test_integration.py` | Выключение observability, `/metrics`, `x-request-id`, HTTP metrics |

Полезные команды:

```bash
poetry run pytest tests/event_log tests/observability
poetry run pytest
```

Frontend-проверка для Tech System UI:

```bash
cd ui/tech-system-ui
npm run build
```

## 11. Безопасность и ограничения

### 11.1. Что уже закрыто

- Audit log хранится в отдельной PostgreSQL БД.
- `event_logs` защищена append-only triggers от `UPDATE` и `DELETE`.
- Password в `/auth/login` body маскируется.
- Bearer token в `authorization` header маскируется.
- Application JSON logs проходят redaction по sensitive keys.
- GlitchTip использует отдельную БД `glitchtip-postgres`.
- OpenSearch bootstrap создает index/template/pattern автоматически.
- Event Logs API требует access token и permission на чтение логов.
- Список Event Logs всегда отдается newest first.

### 11.2. Что важно переопределить на production

Dev defaults нельзя оставлять на реальном сервере:

- `AUTH_JWT_SECRET_KEY`;
- `POSTGRES_PASSWORD`;
- `EVENT_LOG_POSTGRES_PASSWORD`;
- `GLITCHTIP_SECRET_KEY`;
- `GLITCHTIP_ADMIN_PASSWORD`;
- `GLITCHTIP_POSTGRES_PASSWORD`;
- `GRAFANA_ADMIN_PASSWORD`.

OpenSearch сейчас поднят с отключенным security plugin. Для production это надо пересмотреть: сетевые ACL, reverse proxy auth, VPN или включение security.

### 11.3. Текущие ограничения

- Metrics registry самописный in-memory. Он достаточен для текущих counters/gauges/histograms, но не заменяет полноценный `prometheus_client` для сложных production-сценариев.
- Domain-specific metrics по Data/Strategy/GA/Execution пока в основном описаны в спецификации, но реализованы частично.
- OpenTelemetry tracing выключен по умолчанию.
- OTel Collector экспортирует в debug, постоянного trace storage нет.
- Alertmanager не подключен к реальным каналам уведомлений.
- Frontend ошибки в GlitchTip пока не интегрированы через browser SDK.
- Source maps для frontend в GlitchTip не настроены.
- OpenSearch Dashboards и GlitchTip сейчас открываются через direct ports, а не полноценно через gateway subpath.
- Fluent Bit читает Docker logs через `/var/lib/docker/containers`; на некоторых окружениях могут потребоваться права/настройки Docker host.

## 12. Основные файлы реализации

Audit event log:

```text
its/event_log/config.py
its/event_log/models.py
its/event_log/middleware.py
its/event_log/repository.py
its/event_log/router.py
its/event_log/schemas.py
its/event_log/security.py
its/event_log/storage.py
its/event_log/integration.py
services/event_log_backend/app/main.py
```

Observability module:

```text
its/observability/config.py
its/observability/integration.py
its/observability/logging.py
its/observability/metrics.py
its/observability/redaction.py
its/observability/request_context.py
its/observability/tracing.py
```

Infrastructure:

```text
docker-compose.yml
infra/nginx/nginx.conf
infra/observability/prometheus/prometheus.yml
infra/observability/prometheus/alert_rules.yml
infra/observability/alertmanager/alertmanager.yml
infra/observability/grafana/provisioning/datasources/datasources.yml
infra/observability/grafana/dashboards/platform-overview.json
infra/observability/opensearch/bootstrap.sh
infra/observability/opensearch/index-templates/its-app-logs.json
infra/observability/opensearch/ism-policies/technical-logs-retention.json
infra/observability/fluent-bit/fluent-bit.conf
infra/observability/fluent-bit/parsers.conf
infra/observability/otel-collector/config.yml
infra/observability/glitchtip/bootstrap.sh
```

UI:

```text
ui/tech-system-ui/src/api.ts
ui/tech-system-ui/src/App.vue
ui/tech-system-ui/src/styles.css
ui/launchpad-ui/src/App.vue
```

Tests:

```text
tests/event_log/test_middleware.py
tests/event_log/test_repository.py
tests/observability/test_integration.py
```

Related docs:

```text
README.md
dev_specs/its_observability_specification.md
```
