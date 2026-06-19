from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock
import time
from typing import Any


def label_value(value: Any) -> str:
    return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def labels_to_text(labels: tuple[tuple[str, str], ...]) -> str:
    if not labels:
        return ""
    body = ",".join(f'{name}="{label_value(value)}"' for name, value in labels)
    return f"{{{body}}}"


def normalize_labels(labels: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((key, str(value)) for key, value in labels.items()))


@dataclass
class InMemoryMetricsRegistry:
    counters: dict[str, dict[tuple[tuple[str, str], ...], float]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(float))
    )
    gauges: dict[str, dict[tuple[tuple[str, str], ...], float]] = field(
        default_factory=lambda: defaultdict(dict)
    )
    histograms: dict[str, dict[tuple[tuple[str, str], ...], list[float]]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(list))
    )
    lock: Lock = field(default_factory=Lock)

    def inc(self, name: str, labels: dict[str, Any] | None = None, value: float = 1.0) -> None:
        with self.lock:
            self.counters[name][normalize_labels(labels or {})] += value

    def set_gauge(self, name: str, labels: dict[str, Any] | None, value: float) -> None:
        with self.lock:
            self.gauges[name][normalize_labels(labels or {})] = value

    def observe(self, name: str, labels: dict[str, Any] | None, value: float) -> None:
        with self.lock:
            self.histograms[name][normalize_labels(labels or {})].append(value)

    def render(self) -> str:
        lines: list[str] = []
        with self.lock:
            self._render_counters(lines)
            self._render_gauges(lines)
            self._render_histograms(lines)
        return "\n".join(lines) + "\n"

    def _render_counters(self, lines: list[str]) -> None:
        for name, series in sorted(self.counters.items()):
            lines.append(f"# TYPE {name} counter")
            for labels, value in sorted(series.items()):
                lines.append(f"{name}{labels_to_text(labels)} {value}")

    def _render_gauges(self, lines: list[str]) -> None:
        for name, series in sorted(self.gauges.items()):
            lines.append(f"# TYPE {name} gauge")
            for labels, value in sorted(series.items()):
                lines.append(f"{name}{labels_to_text(labels)} {value}")

    def _render_histograms(self, lines: list[str]) -> None:
        buckets = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
        for name, series in sorted(self.histograms.items()):
            lines.append(f"# TYPE {name} histogram")
            for labels, values in sorted(series.items()):
                sorted_values = list(values)
                base_labels = dict(labels)
                count = len(sorted_values)
                total = sum(sorted_values)
                for bucket in buckets:
                    bucket_labels = tuple(
                        sorted({**base_labels, "le": str(bucket)}.items())
                    )
                    bucket_count = sum(1 for item in sorted_values if item <= bucket)
                    lines.append(f"{name}_bucket{labels_to_text(bucket_labels)} {bucket_count}")
                inf_labels = tuple(sorted({**base_labels, "le": "+Inf"}.items()))
                lines.append(f"{name}_bucket{labels_to_text(inf_labels)} {count}")
                lines.append(f"{name}_count{labels_to_text(labels)} {count}")
                lines.append(f"{name}_sum{labels_to_text(labels)} {total}")


REGISTRY = InMemoryMetricsRegistry()


def now_seconds() -> float:
    return time.perf_counter()


def status_class(status_code: int) -> str:
    if status_code <= 0:
        return "unknown"
    return f"{status_code // 100}xx"


def route_template(scope: dict[str, Any]) -> str:
    route = scope.get("route")
    path = getattr(route, "path", None)
    if path:
        return str(path)
    return str(scope.get("path", "unknown"))


def render_metrics() -> str:
    return REGISTRY.render()


def observe_http_request(
    *,
    service: str,
    method: str,
    route: str,
    status_code: int,
    duration_seconds: float,
) -> None:
    labels = {
        "service": service,
        "method": method,
        "route": route,
        "status_code": status_code,
        "status_class": status_class(status_code),
    }
    REGISTRY.inc("its_http_requests_total", labels)
    REGISTRY.observe("its_http_request_duration_seconds", labels, duration_seconds)


def set_request_in_progress(
    *,
    service: str,
    method: str,
    route: str,
    value: float,
) -> None:
    REGISTRY.set_gauge(
        "its_http_requests_in_progress",
        {"service": service, "method": method, "route": route},
        value,
    )


def observe_exception(*, service: str, route: str, exception_type: str) -> None:
    REGISTRY.inc(
        "its_http_exceptions_total",
        {"service": service, "route": route, "exception_type": exception_type},
    )


def observe_audit_event(*, service: str, method: str, result: str) -> None:
    REGISTRY.inc(
        "its_audit_events_total",
        {"service": service, "method": method, "result": result},
    )


def observe_audit_write(
    *,
    service: str,
    result: str,
    duration_seconds: float,
) -> None:
    REGISTRY.observe(
        "its_audit_write_duration_seconds",
        {"service": service, "result": result},
        duration_seconds,
    )


def observe_audit_write_failure(*, service: str, error_type: str) -> None:
    REGISTRY.inc(
        "its_audit_write_failures_total",
        {"service": service, "error_type": error_type},
    )
