# Спецификация развития Observability в ITS

**Продукт:** ITS - Intelligent Trading Strategies  
**Подсистема:** Platform Observability / Logging / Monitoring / Error Tracking  
**Статус документа:** спецификация для разработки  
**Версия:** 1.1  
**Дата:** 2026-06-19

---

## 1. Назначение документа

Документ описывает, как развить текущую подсистему логирования ITS до полноценной open-source observability-платформы.

Цель - не заменить уже реализованный audit log, а правильно разделить разные классы данных:

- **Audit log** - юридически и операционно значимый журнал действий пользователя, append-only, хранится в отдельном PostgreSQL.
- **Operational logs** - технические логи приложений, gateway, фоновых задач и контейнеров, пригодные для поиска, расследования инцидентов и корреляции.
- **Metrics** - числовые показатели состояния системы, пригодные для графиков, SLO и alerting.
- **Traces** - распределенные трассировки запросов между gateway, backend-сервисами, БД и внешними API.
- **Errors** - группировка исключений, stack traces, релизы, source maps, уведомления о регрессиях.
- **Uptime / synthetic checks** - внешняя проверка доступности ключевых endpoints.

Все предлагаемые инструменты должны быть open source и пригодны для self-hosted эксплуатации.

### 1.1. Статус реализации

На 2026-06-19 в репозитории реализован первый рабочий слой:

- добавлен общий модуль `its/observability`;
- observability подключена во все FastAPI backend-сервисы;
- добавлены env-настройки через Pydantic `ObservabilitySettings`;
- добавлен master switch `OBSERVABILITY_ENABLED=true|false`;
- добавлены `/metrics`, `X-Request-ID`, JSON logging, HTTP request metrics;
- добавлены базовые audit metrics для записи event log;
- добавлены Docker Compose сервисы observability в profile `observability`;
- добавлены конфиги Prometheus, Alertmanager, Grafana, OpenSearch, Fluent Bit, OTel Collector;
- текущий PostgreSQL audit log оставлен append-only и не заменен OpenSearch.

Полноценные domain metrics, distributed traces с установленными OpenTelemetry SDK, GlitchTip source maps и production-grade alert routing остаются следующими фазами.

---

## 2. Текущее состояние

В ITS уже реализована собственная подсистема пользовательского аудита:

- общий модуль `its/event_log`;
- middleware `EventLogMiddleware`, подключаемый через `install_event_log(app, service_name=...)`;
- отдельная БД `event-log-postgres` в `docker-compose.yml`;
- отдельный backend `services/event_log_backend`;
- UI в `Tech System` для просмотра Event Logs;
- поля журнала: `id`, `date_time`, `service`, `user`, `http_action`, `ip_address`, `path`, `header`, `body`;
- логирование подключено к `data-backend`, `strategy-backend`, `ga-backend`, `execution-backend`, `tech-system-backend`, `event-log-backend`, legacy `its/app.py`;
- `event_logs` защищен append-only триггерами от `UPDATE` и `DELETE`;
- чувствительные данные уже частично маскируются: `Authorization: Bearer ****`, password в `/auth/login`;
- выборка логов сортируется на backend по `date_time DESC, id DESC`.

Текущий подход хорошо решает задачу аудита действий пользователя, но не закрывает observability промышленного уровня.

---

## 3. Проблема

### 3.1. PostgreSQL audit log не должен быть единственным хранилищем логов

PostgreSQL подходит для append-only аудита с точной структурой и транзакционной надежностью. Но он не является оптимальным основным хранилищем для:

- полнотекстового поиска по техническим логам;
- высокочастотных application logs;
- агрегации логов из контейнеров и gateway;
- дешевого хранения больших объемов технических логов;
- построения log analytics dashboards;
- корреляции логов, метрик и трассировок.

Если писать все технические события в `event_logs`, таблица начнет выполнять две несовместимые роли: audit trail и operational log store.

### 3.2. В текущем аудите не хватает технического контекста

Сейчас audit log фиксирует запрос, но для расследования инцидентов не хватает:

- `status_code`;
- `duration_ms`;
- `request_id`;
- `trace_id`;
- `span_id`;
- `route_template`;
- `response_size`;
- `error_type`;
- `error_message`;
- признака успешности записи в audit log;
- метрик очереди/ошибок самого audit middleware.

### 3.3. Нет центрального мониторинга

Сейчас состояние системы проверяется в основном через `/health` и Docker logs. Не хватает:

- Prometheus metrics endpoints;
- единого Grafana;
- alert rules;
- метрик PostgreSQL;
- метрик контейнеров;
- метрик gateway;
- метрик внешних API;
- метрик долгих задач CPCV, WalkForward, Backtesting, GA и Execution.

### 3.4. Нет выделенного error tracking

Исключения сейчас живут в логах или возвращаются как HTTP-ошибки. Не хватает:

- группировки одинаковых ошибок;
- stack traces с контекстом release/environment;
- уведомлений о новых ошибках;
- source maps для frontend;
- привязки ошибок к пользователю, сервису, endpoint, trace_id.

### 3.5. Нет распределенной трассировки

ITS уже является набором сервисов:

- nginx gateway;
- Data Backend;
- Strategy Backend;
- GA Backend;
- Execution Backend;
- Tech System Backend;
- Event Log Backend;
- PostgreSQL;
- T-Invest API;
- frontend-приложения.

Без trace propagation трудно понять, где именно теряется время: gateway, backend, БД, внешний API, расчет стратегии или запись audit log.

---

## 4. Целевая архитектура

### 4.1. Принцип разделения сигналов

```text
User action audit       -> PostgreSQL event_logs, append-only
Application logs        -> stdout JSON -> Fluent Bit -> OpenSearch
HTTP/runtime metrics    -> /metrics -> Prometheus -> Grafana
Distributed traces      -> OpenTelemetry SDK -> OTel Collector -> trace backend
Exceptions/errors       -> Sentry SDK -> GlitchTip
Dashboards/alerts       -> Grafana + Alertmanager + OpenSearch Dashboards + GlitchTip
```

### 4.2. Audit log остается источником истины по действиям пользователя

`its/event_log` не удаляем. Его роль уточняется:

- фиксировать действия пользователя и неавторизованные действия;
- сохранять append-only поведение;
- хранить полную структуру, нужную для аудита;
- продолжать обслуживать экран `Tech System -> Event Logs`;
- не быть хранилищем технических логов приложения.

Рекомендуемое развитие audit log:

- добавить `status_code`, `duration_ms`, `request_id`, `trace_id`, `route`;
- расширить универсальную маскировку секретов;
- добавить метрики самого audit middleware;
- сделать запись в БД асинхронной через bounded queue, чтобы деградация `event-log-postgres` не блокировала бизнес-запросы;
- добавить отдельный healthcheck доступности audit DB;
- добавить backpressure-метрики и alert, если audit log не успевает записывать события.

### 4.3. Operational logs переезжают в OpenSearch

Все backend-сервисы должны писать structured JSON logs в stdout. Далее:

- Fluent Bit собирает Docker logs;
- нормализует поля;
- маскирует чувствительные данные;
- отправляет в OpenSearch;
- OpenSearch Dashboards используется для поиска и расследований.

OpenSearch должен хранить не audit trail, а технические логи:

- application logs;
- gateway access/error logs;
- worker/background job logs;
- security-relevant technical events;
- pipeline logs самого Fluent Bit / OTel Collector;
- OpenSearch ingestion failures.

### 4.4. Metrics идут в Prometheus

Каждый backend должен иметь `/metrics` endpoint, доступный только внутри docker network.

Prometheus собирает:

- FastAPI application metrics;
- PostgreSQL metrics через `postgres_exporter`;
- container metrics через cAdvisor;
- host metrics через node_exporter, если запуск не только локальный;
- OpenSearch metrics, если включен exporter или compatible endpoint;
- Fluent Bit internal metrics;
- OTel Collector internal metrics;
- nginx metrics через exporter или structured access logs с последующей агрегацией.

Grafana строит dashboards и alerts поверх Prometheus.

### 4.5. Traces идут через OpenTelemetry

OpenTelemetry должен быть единым стандартом инструментирования:

- FastAPI/ASGI instrumentation;
- HTTP client instrumentation;
- SQLAlchemy instrumentation;
- logging correlation через `trace_id`/`span_id`;
- propagation заголовков `traceparent`;
- экспорт в OTel Collector.

Collector нужен как промежуточный слой, чтобы сервисы не зависели от конкретного backend-хранилища.

Для первого этапа можно выбрать один из вариантов trace backend:

1. **Jaeger** - простой OSS backend для distributed tracing.
2. **OpenSearch Trace Analytics через Data Prepper** - если хотим держать logs и traces в OpenSearch-экосистеме.
3. **Grafana Tempo** - если хотим строить LGTM-подход с Grafana как главным интерфейсом.

Для ITS рекомендуется стартовать с OpenTelemetry Collector + Jaeger или OpenSearch Trace Analytics. Выбор зависит от приоритета:

- быстрее внедрить и проще отладить - Jaeger;
- единая OpenSearch-панель для logs/traces - OpenSearch Trace Analytics;
- единая Grafana-панель для metrics/logs/traces - Tempo, но тогда для логов логичнее рассмотреть Loki.

С учетом запроса на OpenSearch как OSS-альтернативу ELK, базовая рекомендация:

```text
Logs       -> OpenSearch
Traces     -> OpenTelemetry Collector -> OpenSearch/Data Prepper или Jaeger
Metrics    -> Prometheus
Dashboards -> Grafana + OpenSearch Dashboards
Errors     -> GlitchTip
```

### 4.6. Errors идут в GlitchTip

GlitchTip используется как open-source Sentry-compatible error tracking:

- self-hosted deployment;
- Python backend через `sentry-sdk`;
- Vue frontend через Sentry browser SDK;
- группировка ошибок;
- stack traces;
- alerts;
- performance monitoring при включенном sampling;
- uptime checks;
- source maps для frontend.

GlitchTip не заменяет OpenSearch и Prometheus. Его роль - ошибки и регрессии, а не общий log analytics.

---

## 5. Выбор инструментов

| Задача | Инструмент | Почему |
| --- | --- | --- |
| Стандарт телеметрии | OpenTelemetry | Единая модель traces, metrics, logs и vendor-neutral экспорт |
| Collector | OpenTelemetry Collector | Batching, retries, redaction/filtering, маршрутизация в разные backend |
| Application logs | JSON logs + Fluent Bit | Легкий сборщик Docker/container logs, поддерживает OpenSearch output |
| Поиск по логам | OpenSearch | OSS search/analytics suite, Apache 2.0, подходит вместо закрытого ELK-подхода |
| Визуализация логов | OpenSearch Dashboards | Поиск, saved searches, dashboards по OpenSearch индексам |
| Метрики | Prometheus | OSS стандарт для pull-based метрик и alerting |
| Alert routing | Alertmanager | Управление алертами, silences, routing |
| Дашборды | Grafana OSS | Единый интерфейс для Prometheus и части logs/traces сценариев |
| Ошибки | GlitchTip | Self-hosted Sentry-compatible error tracking |
| PostgreSQL metrics | postgres_exporter | Готовый exporter для PostgreSQL |
| Container metrics | cAdvisor | Метрики Docker/container runtime |
| Host metrics | node_exporter | CPU, memory, disk, network для Linux hosts |
| Audit trail | Текущий `its/event_log` + PostgreSQL | Уже реализованная append-only бизнес-аудит модель |

---

## 6. Что и где внедрять в репозитории

### 6.1. Новая директория инфраструктуры

Добавить:

```text
infra/observability/
  prometheus/
    prometheus.yml
    alert_rules.yml
  grafana/
    provisioning/
      datasources/
      dashboards/
    dashboards/
      platform-overview.json
      fastapi-services.json
      audit-log-health.json
      data-backend.json
      strategy-backend.json
      ga-backend.json
      execution-backend.json
      postgres.json
      containers.json
  opensearch/
    opensearch.yml
    dashboards.yml
    index-templates/
      its-app-logs.json
      its-nginx-logs.json
      its-audit-copy.json
    ism-policies/
      technical-logs-retention.json
  fluent-bit/
    fluent-bit.conf
    parsers.conf
    filters.conf
  otel-collector/
    config.yml
  glitchtip/
    compose.env.example
```

### 6.2. Docker Compose

Добавлены сервисы в `docker-compose.yml` под profile `observability`:

```text
opensearch
opensearch-dashboards
fluent-bit
otel-collector
prometheus
alertmanager
grafana
postgres-exporter
event-log-postgres-exporter
cadvisor
glitchtip-postgres
glitchtip-redis или valkey
glitchtip-web
glitchtip-worker
```

Запуск:

```text
docker compose --profile observability up --build
```

Это позволит не поднимать тяжелый стек каждый раз при обычной разработке.

### 6.3. Nginx gateway

Целевое состояние: добавить внутренние маршруты только для администраторов или локального контура:

```text
/grafana/          -> grafana
/opensearch/       -> opensearch-dashboards
/glitchtip/        -> glitchtip-web
```

Для production эти маршруты должны быть защищены:

- отдельной сетью;
- basic auth или SSO;
- IP allowlist;
- запретом публичного доступа без TLS.

Текущая реализация не добавляет эти upstream в `infra/nginx/nginx.conf`, потому что observability-сервисы запускаются через optional compose profile. Если добавить upstream без запущенного профиля, обычный `docker compose up --build` может сломаться на резолвинге отсутствующих сервисов. На текущем этапе Grafana, OpenSearch Dashboards и GlitchTip доступны через compose-порты.

### 6.4. Новый Python-модуль `its/observability`

Добавлен общий модуль:

```text
its/observability/
  __init__.py
  config.py
  integration.py
  logging.py
  metrics.py
  tracing.py
  redaction.py
  request_context.py
```

Основная функция:

```python
install_observability(app, service_name="data-backend")
```

Она должна:

- включать request id middleware;
- добавлять metrics middleware;
- добавлять `/metrics`;
- настраивать JSON logging;
- настраивать OpenTelemetry FastAPI instrumentation;
- настраивать SQLAlchemy/HTTP client instrumentation;
- подключать GlitchTip/Sentry SDK при наличии DSN;
- добавлять exception handlers с correlation id.

Текущая реализация делает:

- request id middleware;
- response header `X-Request-ID`;
- `/metrics`;
- HTTP request counter/duration histogram/in-progress gauge;
- exception counter;
- JSON logging с `service`, `environment`, `version`, `request_id`, `trace_id`, `span_id`;
- optional OpenTelemetry hook, если SDK установлен;
- optional GlitchTip/Sentry hook, если `SENTRY_DSN` задан.

Реализованные env-настройки:

| Переменная | Значение по умолчанию | Назначение |
| --- | --- | --- |
| `OBSERVABILITY_ENABLED` | `true` | Главный переключатель observability в приложениях |
| `OBSERVABILITY_ENVIRONMENT` | `dev` | Environment label для logs/errors |
| `OBSERVABILITY_RELEASE` | `1.0.0` | Версия/release |
| `OBSERVABILITY_JSON_LOGS_ENABLED` | `true` | Включает JSON logging |
| `OBSERVABILITY_METRICS_ENABLED` | `true` | Включает `/metrics` и HTTP metrics |
| `OBSERVABILITY_METRICS_PATH` | `/metrics` | Путь metrics endpoint |
| `OBSERVABILITY_TRACING_ENABLED` | `false` | Включает OpenTelemetry instrumentation, если SDK установлен |
| `OBSERVABILITY_ERRORS_ENABLED` | `true` | Включает GlitchTip/Sentry SDK, если DSN задан |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://otel-collector:4317` | Адрес OTel Collector |
| `SENTRY_DSN` | `http://85dc29c1a9b645aaab8680880aea79db@glitchtip-web:8000/1` | GlitchTip/Sentry DSN внутри Docker network |
| `SENTRY_TRACES_SAMPLE_RATE` | `0.01` | Sampling для GlitchTip/Sentry performance traces |

Главный режим "включить/выключить" управляется `OBSERVABILITY_ENABLED`.
Остальные switches нужны для поэтапного включения отдельных сигналов без изменения кода.

`install_event_log` остается отдельной функцией. Порядок подключения:

```python
install_observability(app, service_name="...")
install_event_log(app, service_name="...")
```

Нужно проверить порядок middleware, чтобы `request_id` и `trace_id` были доступны audit middleware.

### 6.5. FastAPI backend-сервисы

Заменить локальные настройки логирования на общий модуль в:

- `services/data_backend/app/main.py`;
- `services/strategy_backend/app/main.py`;
- `its/services/ga_backend/app/main.py`;
- `its/services/execution_backend/app/main.py`;
- `services/tech_system_backend/app/main.py`;
- `services/event_log_backend/app/main.py`;
- `its/app.py`.

Каждый сервис должен иметь:

- `/api/v1/health` - lightweight health;
- `/api/v1/ready` - проверка зависимостей, если нужна;
- `/metrics` или `/api/v1/metrics` - scrape target для Prometheus;
- единые labels: `service`, `environment`, `version`.

### 6.6. Frontend

Во всех Vue UI добавить:

- GlitchTip/Sentry browser SDK;
- `environment`;
- `release`;
- source maps upload в build pipeline;
- capture frontend exceptions;
- capture failed API calls как breadcrumbs;
- correlation id из backend response header, если доступен.

Tech System должен получить будущие кнопки:

- **Event Logs** - текущий audit PostgreSQL UI;
- **Operational Logs** - ссылка/iframe на OpenSearch Dashboards saved search;
- **Monitoring** - ссылка/iframe на Grafana;
- **Errors** - ссылка на GlitchTip;
- **Health** - собственная сводная страница состояния сервисов.

---

## 7. Что заменить

### 7.1. Не заменять

Не заменять текущий `event_log` полностью.

Причина: OpenSearch и GlitchTip не являются append-only audit database. Они подходят для observability, но не должны быть единственным источником аудита пользовательских действий.

Оставить:

- `its/event_log`;
- `services/event_log_backend`;
- `event-log-postgres`;
- `Tech System -> Event Logs`;
- append-only триггеры;
- фильтры и таблицу audit logs.

### 7.2. Заменить подход к техническим логам

Технические логи не должны добавляться в `event_logs`.

Вместо этого:

- backend пишет JSON logs в stdout;
- Fluent Bit собирает stdout;
- OpenSearch хранит и индексирует;
- OpenSearch Dashboards показывает operational logs.

### 7.3. Заменить ad hoc диагностику на метрики

Сейчас состояние сервисов фактически проверяется через `/health` и Docker logs.

Заменить на:

- `/metrics` для каждого сервиса;
- Prometheus scrape config;
- Grafana dashboards;
- Alertmanager rules.

### 7.4. Заменить ручной просмотр исключений на GlitchTip

Исключения backend/frontend должны автоматически попадать в GlitchTip.

Логи по-прежнему пишутся в OpenSearch, но issue lifecycle и группировка ошибок идут через GlitchTip.

---

## 8. Стандарты данных

### 8.1. Общие поля логов

Каждая structured log запись должна иметь:

```json
{
  "timestamp": "2026-06-19T12:00:00.000Z",
  "level": "INFO",
  "service": "strategy-backend",
  "environment": "dev",
  "version": "1.0.0",
  "logger": "services.strategy_backend.app.backtest",
  "message": "backtest completed",
  "request_id": "...",
  "trace_id": "...",
  "span_id": "...",
  "user": "user@example.com",
  "http_method": "POST",
  "http_route": "/api/v1/models/{model_name}/backtest/run",
  "http_status_code": 200,
  "duration_ms": 1234.5
}
```

### 8.2. Запрет высококардинальных labels в metrics

В Prometheus labels нельзя добавлять:

- email;
- user id;
- JWT subject;
- request id;
- trace id;
- raw path с id;
- raw ticker list;
- exception message;
- произвольный query string.

Для metrics использовать только низкокардинальные labels:

- `service`;
- `method`;
- `route`;
- `status_code`;
- `status_class`;
- `operation`;
- `backend`;
- `environment`;
- `result`;
- `broker`;
- `mode` (`paper`, `live`, `stub`).

### 8.3. Redaction policy

Единый redaction-модуль должен маскировать в audit logs, app logs, traces и error context:

- `authorization`;
- `cookie`;
- `set-cookie`;
- `x-api-key`;
- `password`;
- `token`;
- `access_token`;
- `refresh_token`;
- `secret`;
- `client_secret`;
- `tinvest_token`;
- `TINVEST_TOKEN`;
- `TINKOFF_INVEST_API_TOKEN`;
- `EXECUTION_TINVEST_TOKEN`;
- broker account tokens;
- private keys;
- любые поля с suffix/prefix `*_token`, `*_secret`, `*_password`.

Рекомендуемый формат:

```json
{
  "authorization": "Bearer ****",
  "password": "***",
  "tinvest_token": "***"
}
```

Для тел запросов:

- `/auth/login` - маскировать пароль;
- refresh/logout endpoints - маскировать refresh token;
- broker endpoints - маскировать account secrets и broker tokens;
- order endpoints - не маскировать торговые параметры, но не писать broker token и raw authorization.

---

## 9. Метрики

### 9.1. Общие HTTP metrics для всех FastAPI

| Метрика | Тип | Labels | Назначение |
| --- | --- | --- | --- |
| `its_http_requests_total` | Counter | `service`, `method`, `route`, `status_code` | Количество запросов |
| `its_http_request_duration_seconds` | Histogram | `service`, `method`, `route`, `status_code` | Latency |
| `its_http_requests_in_progress` | Gauge | `service`, `method`, `route` | Активные запросы |
| `its_http_request_body_bytes` | Histogram | `service`, `method`, `route` | Размер request body |
| `its_http_response_body_bytes` | Histogram | `service`, `method`, `route`, `status_code` | Размер response body |
| `its_http_exceptions_total` | Counter | `service`, `route`, `exception_type` | Исключения |

### 9.2. Audit log metrics

| Метрика | Тип | Labels | Назначение |
| --- | --- | --- | --- |
| `its_audit_events_total` | Counter | `service`, `method`, `result` | Сколько событий принято middleware |
| `its_audit_write_duration_seconds` | Histogram | `service`, `result` | Время записи в Postgres |
| `its_audit_write_failures_total` | Counter | `service`, `error_type` | Ошибки записи audit log |
| `its_audit_queue_size` | Gauge | `service` | Размер очереди, если будет async queue |
| `its_audit_queue_dropped_total` | Counter | `service`, `reason` | Потерянные audit-события, должно быть 0 |
| `its_audit_body_truncated_total` | Counter | `service`, `route` | Сколько body было обрезано |
| `its_audit_redactions_total` | Counter | `service`, `field` | Сколько чувствительных полей замаскировано |

### 9.3. Auth / RBAC metrics

| Метрика | Тип | Labels |
| --- | --- | --- |
| `its_auth_login_attempts_total` | Counter | `result`, `reason` |
| `its_auth_refresh_attempts_total` | Counter | `result`, `reason` |
| `its_auth_logout_total` | Counter | `result` |
| `its_auth_permission_denied_total` | Counter | `service`, `permission`, `route` |
| `its_auth_role_changes_total` | Counter | `role`, `operation` |
| `its_auth_token_validation_failures_total` | Counter | `service`, `reason` |

### 9.4. Data Backend metrics

| Метрика | Тип | Labels |
| --- | --- | --- |
| `its_data_tinvest_requests_total` | Counter | `operation`, `result` |
| `its_data_tinvest_request_duration_seconds` | Histogram | `operation`, `result` |
| `its_data_cache_hits_total` | Counter | `dataset`, `interval` |
| `its_data_cache_misses_total` | Counter | `dataset`, `interval` |
| `its_data_rows_loaded_total` | Counter | `dataset`, `source` |
| `its_data_rss_load_duration_seconds` | Histogram | `source`, `result` |
| `its_data_prices_requested_days` | Histogram | `interval` |

### 9.5. Strategy Backend metrics

| Метрика | Тип | Labels |
| --- | --- | --- |
| `its_strategy_tests_total` | Counter | `test_type`, `result` |
| `its_strategy_test_duration_seconds` | Histogram | `test_type`, `result` |
| `its_strategy_test_cache_hits_total` | Counter | `test_type` |
| `its_strategy_test_cache_misses_total` | Counter | `test_type` |
| `its_strategy_model_registry_count` | Gauge | `group` |
| `its_strategy_prod_ready_changes_total` | Counter | `result` |
| `its_strategy_external_data_fetch_duration_seconds` | Histogram | `dataset`, `result` |

### 9.6. GA Backend metrics

| Метрика | Тип | Labels |
| --- | --- | --- |
| `its_ga_runs_total` | Counter | `result` |
| `its_ga_runs_active` | Gauge | none |
| `its_ga_run_duration_seconds` | Histogram | `result` |
| `its_ga_generations_total` | Counter | `run_id_bucket` или без run id |
| `its_ga_best_score` | Gauge | `run_status` |
| `its_ga_materialized_models_total` | Counter | `result` |
| `its_ga_run_cache_write_failures_total` | Counter | `error_type` |

Важно: `run_id` нельзя использовать как label в Prometheus из-за высокой кардинальности. Для конкретного run id использовать logs/traces.

### 9.7. Execution Backend metrics

| Метрика | Тип | Labels |
| --- | --- | --- |
| `its_execution_broker_requests_total` | Counter | `operation`, `broker`, `result` |
| `its_execution_broker_request_duration_seconds` | Histogram | `operation`, `broker`, `result` |
| `its_execution_orders_submitted_total` | Counter | `broker`, `side`, `order_type`, `result`, `mode` |
| `its_execution_stop_orders_submitted_total` | Counter | `broker`, `result`, `mode` |
| `its_execution_strategy_runs_total` | Counter | `strategy_type`, `result`, `mode` |
| `its_execution_orderbook_ws_connections` | Gauge | none |
| `its_execution_orderbook_messages_total` | Counter | `result` |
| `its_execution_broker_errors_total` | Counter | `operation`, `error_type` |

### 9.8. Database and infrastructure metrics

Через exporters:

- PostgreSQL active connections;
- long transactions;
- locks;
- deadlocks;
- table/index size;
- slow queries, если включен `pg_stat_statements`;
- event log table growth;
- container CPU/memory;
- restart count;
- disk usage;
- OpenSearch JVM heap, disk watermark, indexing errors;
- Fluent Bit output retries/errors;
- OTel Collector dropped spans/logs/metrics.

---

## 10. Дашборды Grafana

### 10.1. Platform Overview

Назначение - первый экран дежурного инженера.

Панели:

- статус всех backend `/health`;
- request rate по сервисам;
- p50/p95/p99 latency по сервисам;
- 5xx rate;
- 4xx rate;
- active requests;
- container restarts;
- CPU/memory по сервисам;
- PostgreSQL connections;
- audit write failures;
- OpenSearch ingestion failures;
- активные GA runs;
- broker API errors.

### 10.2. FastAPI Services

Переменные:

- `service`;
- `route`;
- `status_code`;
- `environment`.

Панели:

- RPS by route;
- latency histogram p95/p99;
- error rate by route;
- top slow routes;
- exceptions by type;
- request/response body size;
- active requests.

### 10.3. Audit Log Health

Панели:

- audit events per second;
- write duration p95/p99;
- write failures;
- queue size;
- dropped events, должно быть 0;
- body truncations;
- redactions by field;
- event-log PostgreSQL table size;
- event-log PostgreSQL connections;
- newest event age.

Alert:

- `audit_write_failures_total > 0`;
- `audit_queue_dropped_total > 0`;
- newest event older than threshold while traffic exists.

### 10.4. Data Backend

Панели:

- T-Invest request latency/error rate;
- cache hit ratio by dataset;
- prices request duration;
- dividends request duration;
- RSS load result;
- rows loaded;
- external API failures by operation.

### 10.5. Strategy Backend

Панели:

- CPCV/WalkForward/Backtesting runs;
- duration by test type;
- failures by model/test type;
- cache hit ratio;
- generated report size;
- prod-ready changes.

### 10.6. GA Backend

Панели:

- active/queued/completed/failed runs;
- run duration;
- best score over time;
- generation throughput;
- materialized models;
- failures by error type;
- cache write failures.

### 10.7. Execution Backend

Панели:

- broker request latency/error rate;
- submitted orders by result/mode;
- rejected orders;
- stop orders;
- strategy run previews;
- websocket connections;
- orderbook stream errors;
- live/paper split.

Alerts для live-режима должны быть строже, чем для paper/stub.

### 10.8. Auth and Security

Панели:

- login attempts success/failure;
- token refresh failures;
- permission denied by service/permission;
- role changes;
- failed JWT validation;
- unauthenticated access attempts;
- suspicious IPs by audit log/OpenSearch query.

### 10.9. PostgreSQL

Отдельно для основной БД и event-log БД:

- connections;
- locks;
- deadlocks;
- transaction duration;
- table size;
- index size;
- rows inserted per minute;
- vacuum/autovacuum;
- slow query count, если доступно.

### 10.10. OpenSearch / Log Pipeline

Панели:

- indexing rate;
- indexing failures;
- rejected writes;
- disk usage;
- JVM heap;
- search latency;
- index size by pattern;
- Fluent Bit retries/errors;
- Fluent Bit output throughput;
- OTel Collector dropped telemetry.

---

## 11. OpenSearch Dashboards

Создать index patterns:

```text
its-app-logs-*
its-nginx-logs-*
its-otel-logs-*
its-audit-copy-*
```

Saved searches:

- errors by service;
- logs by trace_id;
- logs by request_id;
- auth failures;
- permission denied;
- audit redactions;
- broker errors;
- GA run failures;
- slow strategy tests;
- event-log backend failures.

Рекомендуемые поля для OpenSearch mapping:

```text
@timestamp: date
service: keyword
environment: keyword
version: keyword
level: keyword
logger: keyword
message: text
request_id: keyword
trace_id: keyword
span_id: keyword
user: keyword
http.method: keyword
http.route: keyword
http.status_code: integer
duration_ms: float
error.type: keyword
error.message: text
```

Retention:

- application logs dev: 7-14 дней;
- application logs prod: 30-90 дней;
- nginx logs: 30 дней;
- OpenSearch internal logs: 14-30 дней;
- audit-copy в OpenSearch: не источник истины, retention 30-90 дней;
- PostgreSQL audit log: append-only источник истины, отдельная политика архивации.

---

## 12. GlitchTip

### 12.1. Backend integration

Добавить настройки:

```dotenv
GLITCHTIP_DSN=
SENTRY_DSN=${GLITCHTIP_DSN}
SENTRY_ENVIRONMENT=dev
SENTRY_RELEASE=1.0.0
SENTRY_TRACES_SAMPLE_RATE=0.05
SENTRY_ENABLE_LOGS=false
```

В `its/observability/tracing.py` или отдельном `errors.py`:

```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

sentry_sdk.init(
    dsn=settings.sentry_dsn,
    environment=settings.environment,
    release=settings.release,
    traces_sample_rate=settings.sentry_traces_sample_rate,
    integrations=[
        FastApiIntegration(),
        SqlalchemyIntegration(),
        LoggingIntegration(event_level="ERROR"),
    ],
    send_default_pii=False,
    before_send=redact_sentry_event,
)
```

В контекст добавлять:

- `service`;
- `request_id`;
- `trace_id`;
- `route`;
- `user`, если допустимо и без PII-risk. Для email лучше использовать hashed user id или masked email.

### 12.2. Frontend integration

Для Vue:

- настроить Sentry browser SDK на GlitchTip DSN;
- включить environment/release;
- breadcrumbs для API calls;
- source maps upload;
- `beforeSend` redaction;
- отключить отправку JWT/localStorage.

### 12.3. Uptime checks

GlitchTip можно использовать для простых uptime checks:

- `GET /health`;
- `GET /api/data/health`;
- `GET /api/strategies/health`;
- `GET /api/ga/health`;
- `GET /api/execution/health`;
- `GET /api/tech/health`;
- `GET /api/event-log/health`.

Для глубоких dependency checks лучше использовать Prometheus blackbox exporter или отдельные readiness endpoints.

---

## 13. Alerting

### 13.1. Базовые alerts

| Alert | Условие | Severity |
| --- | --- | --- |
| ServiceDown | `up == 0` | critical |
| High5xxRate | 5xx > 2% за 5 минут | warning/critical |
| HighLatencyP95 | p95 выше SLO | warning |
| AuditWriteFailed | audit write failures > 0 | critical |
| AuditEventsDropped | dropped audit events > 0 | critical |
| EventLogDbDown | event-log PostgreSQL недоступен | critical |
| MainDbDown | основной PostgreSQL недоступен | critical |
| OpenSearchIngestionFailed | Fluent Bit/OpenSearch write errors | warning |
| DiskSpaceLow | disk free < 15% | warning |
| ContainerRestarting | restart count растет | warning |
| BrokerApiFailures | broker errors выше threshold | critical для live |
| FailedLoginSpike | login failures spike | warning |
| PermissionDeniedSpike | permission denied spike | warning |
| GARunFailureSpike | GA failures spike | warning |

### 13.2. SLO-ориентированные targets

Для начального этапа:

- API availability: 99% для local/prod-like контура;
- p95 latency для обычных API: < 500 ms;
- p95 latency для тяжелых расчетов не нормировать как обычный HTTP, вместо этого измерять job duration;
- audit event loss: 0;
- audit write failure: 0;
- live execution order submission errors: отдельный critical alert.

---

## 14. План внедрения

### Фаза 0. Зафиксировать границы

Результат:

- принято решение, что PostgreSQL `event_logs` остается audit trail;
- OpenSearch не заменяет audit DB;
- Prometheus/Grafana отвечают за metrics и dashboards;
- GlitchTip отвечает за exception/error lifecycle;
- OpenTelemetry отвечает за трассировки и correlation.

### Фаза 1. Базовая инфраструктура

Статус: базово реализовано.

Сделать:

1. Добавить `infra/observability`.
2. Добавить compose profile `observability`.
3. Поднять Prometheus, Grafana, Alertmanager.
4. Поднять postgres exporters для основной и event-log БД.
5. Поднять cAdvisor.
6. Подготовить Grafana provisioning.
7. Подготовить первый dashboard `Platform Overview`.

Критерий готовности:

- `docker compose --profile observability up --build` поднимается;
- Grafana видит Prometheus datasource;
- Prometheus видит backend scrape targets и exporters.

### Фаза 2. Общий metrics middleware

Статус: базово реализовано.

Сделать:

1. Создать `its/observability`.
2. Реализовать `install_observability`.
3. Добавить HTTP metrics middleware.
4. Добавить `/metrics`.
5. Подключить ко всем FastAPI сервисам.
6. Написать tests на route normalization и отсутствие high-cardinality labels.

Критерий готовности:

- все backend-сервисы отдают metrics;
- Prometheus собирает HTTP request metrics;
- Grafana показывает latency/error rate по сервисам.

### Фаза 3. Structured logs и OpenSearch

Статус: инфраструктура и JSON logging добавлены. Production redaction/filtering в Fluent Bit и saved searches требуют отдельной доработки.

Сделать:

1. Настроить JSON logging для Python.
2. Добавить `request_id`, `trace_id`, `span_id` в log context.
3. Поднять OpenSearch и OpenSearch Dashboards.
4. Поднять Fluent Bit.
5. Настроить сбор Docker logs.
6. Настроить OpenSearch index templates и retention policy.
7. Добавить saved searches.

Критерий готовности:

- backend logs доступны в OpenSearch Dashboards;
- можно искать по `service`, `request_id`, `trace_id`, `level`;
- чувствительные поля маскируются до попадания в OpenSearch.

### Фаза 4. Улучшить audit log

Статус: базовые audit write metrics добавлены. Новые поля audit table (`status_code`, `duration_ms`, `request_id`, `trace_id`, `route`) еще не добавлены.

Сделать:

1. Добавить поля `status_code`, `duration_ms`, `request_id`, `trace_id`, `route`.
2. Расширить redaction на все секреты.
3. Добавить audit metrics.
4. Добавить dashboard `Audit Log Health`.
5. Добавить alert на failures/drops.
6. Рассмотреть async bounded queue для записи audit events.

Критерий готовности:

- audit UI продолжает работать;
- новые поля доступны в таблице и фильтрах;
- audit write failures видны в Prometheus/Grafana;
- audit loss равен 0.

### Фаза 5. OpenTelemetry traces

Статус: добавлен optional hook в `its/observability/tracing.py`; для полноценной работы нужно добавить Python зависимости OpenTelemetry SDK/instrumentations и выбрать trace backend.

Сделать:

1. Поднять OTel Collector.
2. Добавить FastAPI instrumentation.
3. Добавить HTTP client instrumentation.
4. Добавить SQLAlchemy instrumentation.
5. Прокинуть `traceparent` через nginx и backend calls.
6. Выбрать trace backend: Jaeger или OpenSearch Trace Analytics.
7. Связать logs с traces через `trace_id`.

Критерий готовности:

- запрос из UI к backend имеет trace;
- backend -> Data Backend или broker API вызовы видны как spans;
- logs можно отфильтровать по trace_id.

### Фаза 6. GlitchTip

Статус: Docker Compose сервисы добавлены, backend hook через optional `sentry_sdk` добавлен. Frontend SDK и source maps еще не реализованы.

Сделать:

1. Поднять self-hosted GlitchTip.
2. Настроить backend `sentry_sdk`.
3. Настроить frontend SDK.
4. Настроить source maps upload.
5. Добавить release/environment.
6. Настроить alerts по новым ошибкам.
7. Добавить Tech System кнопку `Errors`.

Критерий готовности:

- backend exception появляется в GlitchTip;
- frontend exception появляется в GlitchTip;
- stack trace читаемый;
- source maps работают для production frontend build.

### Фаза 7. Domain metrics

Сделать:

1. Добавить Data Backend external API/cache metrics.
2. Добавить Strategy Backend test metrics.
3. Добавить GA run metrics.
4. Добавить Execution broker/order metrics.
5. Добавить Auth/RBAC metrics.
6. Создать domain dashboards.

Критерий готовности:

- есть отдельные dashboards для Data, Strategy, GA, Execution, Auth;
- есть alerts для live execution и audit failures;
- тяжелые расчеты видны как jobs, а не только как долгие HTTP requests.

### Фаза 8. Tech System Observability Hub

Статус: частично реализовано. На главном экране Tech System добавлены карточки `Grafana`, `OpenSearch`, `GlitchTip` с URL через `VITE_GRAFANA_URL`, `VITE_OPENSEARCH_DASHBOARDS_URL`, `VITE_GLITCHTIP_URL` и дефолтами на локальные compose-порты. Полноценные permission checks для новых observability-кнопок и отдельный Health view еще не реализованы.

Сделать:

1. В Tech System оставить плитку/кнопку `Event Logs`.
2. Добавить кнопки:
   - `Operational Logs`;
   - `Monitoring`;
   - `Errors`;
   - `Health`.
3. Реализовать role/permission checks:
   - `system.logs.read`;
   - `system.monitoring.read`;
   - `system.errors.read`;
   - `system.health.read`.
4. Не встраивать админские панели без защиты, если gateway открыт наружу.

Критерий готовности:

- Tech System становится центральной точкой входа в observability;
- Event Logs по-прежнему открывает audit UI;
- остальные кнопки ведут в OpenSearch/Grafana/GlitchTip/Health.

---

## 15. Что еще не хватает с точки зрения Observability

### 15.1. Correlation id contract

Нужно ввести единый контракт:

- `X-Request-ID` принимается от gateway/client или генерируется backend;
- `X-Request-ID` возвращается в response;
- `traceparent` используется для distributed tracing;
- `request_id` и `trace_id` пишутся в audit log, app logs, error tracking.

### 15.2. Версионирование и release tracking

Добавить:

- `ITS_VERSION`;
- git commit SHA в build args;
- `/version` endpoint;
- label `version` в logs/metrics/traces/errors;
- GlitchTip releases.

### 15.3. Readiness checks

`/health` оставить легким. Добавить `/ready`:

- основная БД доступна;
- event-log БД доступна;
- внешняя зависимость доступна, если endpoint не слишком дорогой;
- кэш-директории доступны на запись;
- broker mode корректно сконфигурирован.

### 15.4. Runbook-документация

Для каждого critical alert нужен runbook:

- что значит alert;
- где смотреть dashboard;
- какие logs искать;
- какие команды запускать;
- как отличить проблему данных от проблемы кода;
- когда останавливать live execution.

Предложенный путь:

```text
docs/runbooks/
  audit-log-write-failed.md
  postgres-down.md
  opensearch-ingestion-failed.md
  broker-api-failures.md
  ga-run-failures.md
  high-api-latency.md
```

### 15.5. Data quality observability

Для trading-системы обычных технических метрик недостаточно. Нужны data quality checks:

- свежесть котировок;
- пропущенные свечи;
- аномальные цены;
- резкое изменение числа инструментов;
- пустые dividends/prices responses;
- задержка RSS загрузки;
- расхождение broker prices и stored prices.

### 15.6. Trading safety observability

Для будущего live execution:

- отдельные critical alerts на live order failures;
- лимиты order count / notional exposure;
- мониторинг отклонения target weights от actual positions;
- мониторинг rejected/cancelled orders;
- мониторинг stop order coverage;
- heartbeat broker connection;
- audit trail для всех live действий с повышенной защитой.

### 15.7. Cost and capacity observability

Даже self-hosted OSS стек имеет стоимость ресурсов:

- рост `event_logs`;
- рост OpenSearch indices;
- disk watermark;
- Prometheus retention;
- Grafana dashboard load;
- размер source maps/artifacts;
- объем traces при высоком sampling.

Нужны retention policies и capacity dashboard.

---

## 16. Критерии готовности всей программы

Observability считается внедренной, когда:

- audit log продолжает быть append-only и доступен в Tech System;
- каждый backend имеет metrics endpoint;
- Prometheus собирает метрики всех сервисов и БД;
- Grafana показывает Platform Overview и domain dashboards;
- app logs попадают в OpenSearch в JSON-структуре;
- logs можно искать по `service`, `request_id`, `trace_id`;
- ошибки backend/frontend попадают в GlitchTip;
- есть distributed trace хотя бы для основных HTTP запросов;
- чувствительные данные маскируются в audit logs, app logs, traces и errors;
- настроены базовые alerts;
- есть runbooks для critical alerts;
- Tech System имеет отдельные входы в Event Logs, Monitoring, Operational Logs, Errors и Health.

---

## 17. Источники

- OpenTelemetry: https://opentelemetry.io/docs/what-is-opentelemetry/
- OpenTelemetry Collector: https://opentelemetry.io/docs/collector/
- OpenTelemetry Python auto-instrumentation: https://opentelemetry.io/docs/zero-code/python/
- OpenTelemetry HTTP semantic conventions: https://opentelemetry.io/docs/specs/semconv/http/http-metrics/
- Prometheus overview: https://prometheus.io/docs/introduction/overview/
- Prometheus client libraries: https://prometheus.io/docs/instrumenting/clientlibs/
- Prometheus metric naming: https://prometheus.io/docs/practices/naming/
- Prometheus histograms: https://prometheus.io/docs/practices/histograms/
- Grafana OSS documentation: https://grafana.com/docs/grafana/latest/introduction/
- OpenSearch FAQ: https://opensearch.org/faq/
- OpenSearch documentation: https://docs.opensearch.org/latest/
- Fluent Bit overview: https://docs.fluentbit.io/manual/about/what-is-fluent-bit
- Fluent Bit OpenSearch output: https://docs.fluentbit.io/manual/data-pipeline/outputs/opensearch
- GlitchTip documentation: https://glitchtip.com/documentation/
- GlitchTip installation: https://glitchtip.com/documentation/install/
- GlitchTip SDK documentation: https://glitchtip.com/sdkdocs/
- GlitchTip logs: https://glitchtip.com/documentation/logs/
- postgres_exporter: https://github.com/prometheus-community/postgres_exporter
- cAdvisor guide: https://prometheus.io/docs/guides/cadvisor/

---

## 18. Команды запуска

Обычный запуск системы:

```bash
docker compose up --build
```

Запуск системы вместе с observability stack:

```bash
docker compose --profile observability up --build
```

Выключить observability в backend-приложениях:

```bash
OBSERVABILITY_ENABLED=false docker compose up --build
```

Включить metrics и JSON logs, но оставить traces/errors выключенными:

```bash
OBSERVABILITY_ENABLED=true \
OBSERVABILITY_METRICS_ENABLED=true \
OBSERVABILITY_JSON_LOGS_ENABLED=true \
OBSERVABILITY_TRACING_ENABLED=false \
OBSERVABILITY_ERRORS_ENABLED=false \
docker compose --profile observability up --build
```

Локальные UI observability по умолчанию:

- Grafana через gateway: `http://localhost:8080/grafana/`;
- OpenSearch API через gateway: `http://localhost:8080/opensearch-api/`;
- OpenSearch Dashboards: `http://localhost:5601/app/home`;
- GlitchTip: `http://localhost:8001/`.

OpenSearch bootstrap выполняется автоматически отдельным one-shot контейнером `opensearch-bootstrap`. Он должен быть частью Docker Compose profile `observability` и обязан создавать без ручных действий:

- ISM policy `technical-logs-retention`;
- index template `its-app-logs` для индексов `its-app-logs-*`;
- стартовый дневной индекс `its-app-logs-YYYY.MM.DD`;
- OpenSearch Dashboards index pattern `its-app-logs-*`;
- default index pattern в OpenSearch Dashboards.

GlitchTip должен использовать отдельную PostgreSQL БД `glitchtip-postgres`. Перед стартом `glitchtip-web` и `glitchtip-worker` должен выполняться one-shot контейнер `glitchtip-migrate`, который:

- применяет Django migrations GlitchTip;
- создает или обновляет bootstrap admin;
- создает default organization, owner membership, team, project и project key;
- блокирует старт web/worker до успешного завершения миграций.

Dev-доступ по умолчанию: `admin@example.com` / `admin123`. Значения должны переопределяться через `GLITCHTIP_ADMIN_EMAIL` и `GLITCHTIP_ADMIN_PASSWORD`; пароль должен быть не короче 8 символов.
Default organization/team/project должны настраиваться через `GLITCHTIP_BOOTSTRAP_ORGANIZATION`, `GLITCHTIP_BOOTSTRAP_TEAM`, `GLITCHTIP_BOOTSTRAP_PROJECT`.
Default project key должен быть стабильным и настраиваться через `GLITCHTIP_PROJECT_PUBLIC_KEY`, чтобы backend-сервисы могли получить рабочий `SENTRY_DSN` без ручного копирования DSN из UI.
