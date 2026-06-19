from __future__ import annotations

from datetime import UTC, datetime
import json
import logging
from typing import Any

from its.observability.config import ObservabilitySettings
from its.observability.request_context import (
    request_id_var,
    service_name_var,
    span_id_var,
    trace_id_var,
)
from its.observability.redaction import redact_mapping


class JsonLogFormatter(logging.Formatter):
    def __init__(self, *, environment: str, release: str) -> None:
        super().__init__()
        self.environment = environment
        self.release = release

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "service": service_name_var.get(),
            "environment": self.environment,
            "version": self.release,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(),
            "trace_id": trace_id_var.get(),
            "span_id": span_id_var.get(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(redact_mapping(payload), ensure_ascii=False, default=str)


def configure_json_logging(settings: ObservabilitySettings, *, service_name: str) -> None:
    service_name_var.set(service_name)
    root = logging.getLogger()
    formatter = JsonLogFormatter(
        environment=settings.environment,
        release=settings.release,
    )
    if not root.handlers:
        handler = logging.StreamHandler()
        root.addHandler(handler)
    for handler in root.handlers:
        handler.setFormatter(formatter)
    root.setLevel(logging.INFO)
