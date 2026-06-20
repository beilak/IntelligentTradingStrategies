# Execution and Technical Services

[Back to Contents](README.md)

## Purpose

Execution and Tech System cover the workflow after strategy research: user management, access control, broker accounts, trading-strategy assignments, and controlled order submission. These modules do not replace production risk management, but they provide a working interface for checking a strategy against a real broker circuit or in safe `stub` mode.

## Execution

Execution consists of:

| Component | Path | Purpose |
| --- | --- | --- |
| Backend | `its/services/execution_backend` | accounts, orders, order book, and strategy-run API |
| Domain | `its/execution` | order schemas, configuration, T-Invest service, and strategy runner |
| UI | `ui/execution-ui` | accounts, portfolio, orders, and assigned strategies |

Main capabilities:

- read configured T-Invest accounts;
- account overview: portfolio, positions, orders, stop orders, operations, limits, and margin attributes;
- create market/limit orders and stop-loss/take-profit stop orders;
- retrieve last price and WebSocket order book;
- assign `prod-ready` trading strategies to an account;
- run a strategy with order calculation by period, interval, `order_type`, `limit_offset_pct`, and `min_order_value`.

Key variables:

```dotenv
EXECUTION_TINVEST_ACCOUNT_IDS=account_id_1,account_id_2
EXECUTION_TINVEST_ACCOUNTS=account_id_1:Main,account_id_2:IIS
EXECUTION_ORDER_SUBMISSION_MODE=stub
```

Use `stub` for demonstrations: the ticket is validated but not sent to the broker. In `real` mode the backend sends the order through the T-Invest API.

## Tech System

Tech System controls access to protected functions:

- registration and login;
- access/refresh JWT tokens;
- roles, permissions, and user role assignment;
- role requests and approval;
- login and RBAC audit events.

The UI is available at `/tech/auth/`, and the API is available at `/api/tech/`. Execution UI uses these tokens and redirects the user to login when the session is missing or expired.

## Event Log

Event Log stores user and API actions in a separate `event-log-postgres` database. `/api/event-log/events` supports filtering by service, user, HTTP method, path, IP, headers, request body, and period. Tech System UI uses this API to display the action log.

## Observability

The `observability` profile adds Prometheus, Grafana, OpenSearch, Fluent Bit, OpenTelemetry Collector, and GlitchTip. Backend services publish `/metrics`, write JSON logs, and send errors to GlitchTip when the corresponding environment variables are enabled.
