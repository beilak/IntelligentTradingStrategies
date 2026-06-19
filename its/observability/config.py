from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ObservabilitySettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", populate_by_name=True)

    enabled: bool = Field(default=True, alias="OBSERVABILITY_ENABLED")
    environment: str = Field(default="dev", alias="OBSERVABILITY_ENVIRONMENT")
    release: str = Field(default="1.0.0", alias="OBSERVABILITY_RELEASE")
    json_logs_enabled: bool = Field(default=True, alias="OBSERVABILITY_JSON_LOGS_ENABLED")
    metrics_enabled: bool = Field(default=True, alias="OBSERVABILITY_METRICS_ENABLED")
    metrics_path: str = Field(default="/metrics", alias="OBSERVABILITY_METRICS_PATH")
    tracing_enabled: bool = Field(default=False, alias="OBSERVABILITY_TRACING_ENABLED")
    otlp_endpoint: str | None = Field(default=None, alias="OTEL_EXPORTER_OTLP_ENDPOINT")
    errors_enabled: bool = Field(default=False, alias="OBSERVABILITY_ERRORS_ENABLED")
    sentry_dsn: str | None = Field(default=None, alias="SENTRY_DSN")
    sentry_traces_sample_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        alias="SENTRY_TRACES_SAMPLE_RATE",
    )


@lru_cache
def get_observability_settings() -> ObservabilitySettings:
    return ObservabilitySettings()
