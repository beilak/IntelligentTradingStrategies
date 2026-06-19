from __future__ import annotations

import logging

from fastapi import FastAPI

from its.observability.config import ObservabilitySettings

logger = logging.getLogger(__name__)


def configure_tracing(app: FastAPI, settings: ObservabilitySettings, *, service_name: str) -> None:
    if not settings.tracing_enabled:
        return
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry import trace
    except ImportError:
        logger.warning("OpenTelemetry SDK is not installed; tracing is disabled")
        return

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    if settings.otlp_endpoint:
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.otlp_endpoint))
        )
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)


def configure_error_tracking(settings: ObservabilitySettings, *, service_name: str) -> None:
    if not settings.errors_enabled or not settings.sentry_dsn:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    except ImportError:
        logger.warning("sentry-sdk is not installed; GlitchTip/Sentry tracking is disabled")
        return

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
    )
    sentry_sdk.set_tag("service", service_name)
