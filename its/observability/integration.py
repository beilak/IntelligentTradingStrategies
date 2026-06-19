from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from its.observability.config import get_observability_settings
from its.observability.logging import configure_json_logging
from its.observability.metrics import (
    now_seconds,
    observe_exception,
    observe_http_request,
    render_metrics,
    route_template,
    set_request_in_progress,
)
from its.observability.request_context import (
    request_id_var,
    service_name_var,
    span_id_var,
    trace_id_var,
)
from its.observability.tracing import configure_error_tracking, configure_tracing

logger = logging.getLogger(__name__)


def install_observability(app: FastAPI, *, service_name: str) -> None:
    settings = get_observability_settings()
    service_name_var.set(service_name)
    if not settings.enabled:
        return

    if settings.json_logs_enabled:
        configure_json_logging(settings, service_name=service_name)
    configure_error_tracking(settings, service_name=service_name)
    configure_tracing(app, settings, service_name=service_name)

    app.add_middleware(ObservabilityMiddleware, service_name=service_name)

    if settings.metrics_enabled:
        metrics_path = settings.metrics_path

        @app.get(metrics_path, include_in_schema=False)
        async def metrics() -> Response:
            return Response(render_metrics(), media_type="text/plain; version=0.0.4")


class ObservabilityMiddleware:
    def __init__(self, app: ASGIApp, service_name: str) -> None:
        self.app = app
        self.service_name = service_name

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = str(scope.get("method", ""))
        status_code = 500
        request_id = _request_id(scope)
        trace_id, span_id = _trace_context(scope)
        token_request = request_id_var.set(request_id)
        token_service = service_name_var.set(self.service_name)
        token_trace = trace_id_var.set(trace_id)
        token_span = span_id_var.set(span_id)
        started = now_seconds()

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message.get("status", 500))
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode("latin-1")))
                message["headers"] = headers
            await send(message)

        try:
            set_request_in_progress(
                service=self.service_name,
                method=method,
                route=str(scope.get("path", "unknown")),
                value=1.0,
            )
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            observe_exception(
                service=self.service_name,
                route=route_template(scope),
                exception_type=type(exc).__name__,
            )
            logger.exception("Unhandled request exception")
            raise
        finally:
            route = route_template(scope)
            observe_http_request(
                service=self.service_name,
                method=method,
                route=route,
                status_code=status_code,
                duration_seconds=now_seconds() - started,
            )
            set_request_in_progress(
                service=self.service_name,
                method=method,
                route=route,
                value=0.0,
            )
            request_id_var.reset(token_request)
            service_name_var.reset(token_service)
            trace_id_var.reset(token_trace)
            span_id_var.reset(token_span)


def _request_id(scope: Scope) -> str:
    headers = _headers(scope)
    request_id = headers.get("x-request-id")
    return request_id.strip() if request_id else uuid.uuid4().hex


def _trace_context(scope: Scope) -> tuple[str | None, str | None]:
    traceparent = _headers(scope).get("traceparent", "")
    parts = traceparent.split("-")
    if len(parts) >= 4 and len(parts[1]) == 32 and len(parts[2]) == 16:
        return parts[1], parts[2]
    return None, None


def _headers(scope: Scope) -> dict[str, str]:
    return {
        key.decode("latin-1").lower(): value.decode("latin-1", errors="replace")
        for key, value in scope.get("headers", [])
    }
