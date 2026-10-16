"""Environment-backed application settings."""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite+pysqlite:///./inventory.db"
    log_level: str = "INFO"

    @field_validator("database_url")
    @classmethod
    def nonempty_database_url(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("database_url cannot be blank")
        return value.strip()

    @field_validator("log_level")
    @classmethod
    def valid_log_level(cls, value: str) -> str:
        value = value.upper().strip()
        if value not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("log_level must be DEBUG, INFO, WARNING, ERROR or CRITICAL")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
