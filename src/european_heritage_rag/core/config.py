"""Validated runtime configuration for HeritageRAG."""

from enum import StrEnum
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnvironment(StrEnum):
    """Supported application environments."""

    LOCAL = "local"
    TEST = "test"
    PRODUCTION = "production"


class LogLevel(StrEnum):
    """Supported application log levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AppSettings(BaseSettings):
    """Configuration loaded from environment variables and the root .env file."""

    app_env: AppEnvironment = AppEnvironment.LOCAL
    log_level: LogLevel = LogLevel.INFO

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        frozen=True,
    )


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Return the process-wide singleton settings instance."""

    return AppSettings()