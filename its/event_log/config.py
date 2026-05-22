from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_EVENT_LOG_DATABASE_URL = (
    "postgresql+psycopg://its_event_log:its_event_log_password"
    "@localhost:5433/its_event_log"
)


class EventLogSettings(BaseSettings):
    database_url: str = Field(
        default=DEFAULT_EVENT_LOG_DATABASE_URL,
        alias="EVENT_LOG_DATABASE_URL",
    )
    max_body_bytes: int = Field(default=5 * 1024 * 1024, alias="EVENT_LOG_MAX_BODY_BYTES")

    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", populate_by_name=True
    )


@lru_cache
def get_event_log_settings() -> EventLogSettings:
    return EventLogSettings()

