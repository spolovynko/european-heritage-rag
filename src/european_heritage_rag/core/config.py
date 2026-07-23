"""Validated runtime configuration for HeritageRAG."""

from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import AnyHttpUrl, Field
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

    wellcome_catalogue_base_url: AnyHttpUrl = AnyHttpUrl(
        "https://api.wellcomecollection.org/catalogue/v2/"
    )
    wellcome_user_agent: str = Field(
        default="HeritageRAG/0.1.0",
        min_length=1,
    )

    wellcome_connect_timeout_seconds: float = Field(
        default=5.0,
        gt=0,
        le=300,
    )
    wellcome_read_timeout_seconds: float = Field(
        default=30.0,
        gt=0,
        le=300,
    )
    wellcome_write_timeout_seconds: float = Field(
        default=30.0,
        gt=0,
        le=300,
    )
    wellcome_pool_timeout_seconds: float = Field(
        default=5.0,
        gt=0,
        le=300,
    )

    wellcome_max_attempts: int = Field(
        default=4,
        ge=1,
        le=10,
    )
    wellcome_max_retry_wait_seconds: float = Field(
        default=8.0,
        gt=0,
        le=60,
    )

    ingestion_state_directory: Path = Path("var/ingestion")
    bronze_data_directory: Path = Path("data/bronze")

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
