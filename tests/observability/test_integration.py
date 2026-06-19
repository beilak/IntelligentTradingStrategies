from fastapi import FastAPI
from fastapi.testclient import TestClient

from its.observability.config import get_observability_settings
from its.observability.integration import install_observability
from its.observability.metrics import REGISTRY


def clear_settings_cache() -> None:
    get_observability_settings.cache_clear()


def reset_metrics() -> None:
    with REGISTRY.lock:
        REGISTRY.counters.clear()
        REGISTRY.gauges.clear()
        REGISTRY.histograms.clear()


def test_observability_can_be_disabled(monkeypatch) -> None:
    monkeypatch.setenv("OBSERVABILITY_ENABLED", "false")
    clear_settings_cache()

    app = FastAPI()
    install_observability(app, service_name="test-service")

    client = TestClient(app)
    response = client.get("/metrics")

    assert response.status_code == 404


def test_metrics_endpoint_and_request_id(monkeypatch) -> None:
    monkeypatch.setenv("OBSERVABILITY_ENABLED", "true")
    monkeypatch.setenv("OBSERVABILITY_METRICS_ENABLED", "true")
    monkeypatch.setenv("OBSERVABILITY_JSON_LOGS_ENABLED", "false")
    clear_settings_cache()
    reset_metrics()

    app = FastAPI()
    install_observability(app, service_name="test-service")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(app)
    health_response = client.get("/health", headers={"X-Request-ID": "req-1"})
    metrics_response = client.get("/metrics")

    assert health_response.status_code == 200
    assert health_response.headers["x-request-id"] == "req-1"
    assert metrics_response.status_code == 200
    assert "its_http_requests_total" in metrics_response.text
    assert 'service="test-service"' in metrics_response.text
