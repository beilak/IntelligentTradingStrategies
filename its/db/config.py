from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATABASE_URL = "postgresql+psycopg://its:its_password@localhost:5432/its"


class DatabaseSettings(BaseSettings):
    database_url: str = Field(default=DEFAULT_DATABASE_URL, alias="DATABASE_URL")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_database_settings() -> DatabaseSettings:
    return DatabaseSettings()


def get_database_url() -> str:
    return get_database_settings().database_url
