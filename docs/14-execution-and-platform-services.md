# Execution и технические сервисы

[К оглавлению](README.md)

## Назначение

Execution и Tech System закрывают контур после исследования стратегии: управление пользователями, доступом, брокерскими счетами, назначением trading strategies и контролируемой отправкой заявок. Эти модули не заменяют промышленный риск-менеджмент, но дают рабочий интерфейс для проверки стратегии на реальном брокерском контуре или в безопасном `stub` режиме.

## Execution

Execution состоит из:

| Компонент | Путь | Назначение |
| --- | --- | --- |
| Backend | `its/services/execution_backend` | API счетов, заявок, order book и запусков стратегий |
| Domain | `its/execution` | схемы заявок, конфигурация, сервис T-Invest и strategy runner |
| UI | `ui/execution-ui` | интерфейс счетов, портфеля, заявок и назначенных стратегий |

Основные возможности:

- чтение списка настроенных счетов T-Invest;
- обзор счета: портфель, позиции, заявки, stop-заявки, операции, лимиты и маржинальные атрибуты;
- создание market/limit заявок и stop-loss/take-profit stop-заявок;
- получение последней цены и WebSocket order book;
- назначение `prod-ready` trading strategies на счет;
- запуск стратегии с расчетом заявок по параметрам периода, интервала, `order_type`, `limit_offset_pct` и `min_order_value`.

Ключевые переменные:

```dotenv
EXECUTION_TINVEST_ACCOUNT_IDS=account_id_1,account_id_2
EXECUTION_TINVEST_ACCOUNTS=account_id_1:Main,account_id_2:IIS
EXECUTION_ORDER_SUBMISSION_MODE=stub
```

Для демонстраций используйте `stub`: заявка валидируется, но не отправляется брокеру. В режиме `real` backend отправляет заявку через T-Invest API.

## Tech System

Tech System отвечает за доступ к защищенным функциям:

- регистрация и вход;
- access/refresh JWT tokens;
- роли, permissions и назначение ролей пользователям;
- заявки на роли и их согласование;
- аудит событий входа и RBAC.

UI доступен по `/tech/auth/`, API - по `/api/tech/`. Execution UI использует эти токены и перенаправляет пользователя на вход, если сессия отсутствует или истекла.

## Event Log

Event Log сохраняет пользовательские и API-действия в отдельную БД `event-log-postgres`. API `/api/event-log/events` поддерживает фильтрацию по сервису, пользователю, HTTP-методу, пути, IP, заголовкам, телу запроса и периоду. Tech System UI использует этот API для просмотра журнала.

## Observability

Профиль `observability` добавляет Prometheus, Grafana, OpenSearch, Fluent Bit, OpenTelemetry Collector и GlitchTip. Backend-сервисы публикуют `/metrics`, пишут JSON-логи и отправляют ошибки в GlitchTip при включенных переменных окружения.
