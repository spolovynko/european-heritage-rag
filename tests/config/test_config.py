"""Tests for application configuration."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from european_heritage_rag.core.config import (
    AppEnvironment,
    AppSettings,
    LogLevel,
    get_settings,
)

_SETTINGS_ENVIRONMENT_VARIABLES = (
    "APP_ENV",
    "LOG_LEVEL",
    "WELLCOME_CATALOGUE_BASE_URL",
    "WELLCOME_USER_AGENT",
    "WELLCOME_CONNECT_TIMEOUT_SECONDS",
    "WELLCOME_READ_TIMEOUT_SECONDS",
    "WELLCOME_WRITE_TIMEOUT_SECONDS",
    "WELLCOME_POOL_TIMEOUT_SECONDS",
    "WELLCOME_MAX_ATTEMPTS",
    "WELLCOME_MAX_RETRY_WAIT_SECONDS",
    "INGESTION_STATE_DIRECTORY",
    "BRONZE_DATA_DIRECTORY",
    "SILVER_DATA_DIRECTORY",
)


def clear_settings_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove settings overrides that could make a default test machine-specific."""

    for variable in _SETTINGS_ENVIRONMENT_VARIABLES:
        monkeypatch.delenv(variable, raising=False)


def test_settings_use_safe_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings should use documented defaults without external configuration."""

    clear_settings_environment(monkeypatch)

    settings = AppSettings(_env_file=None)

    assert settings.app_env is AppEnvironment.LOCAL
    assert settings.log_level is LogLevel.INFO
    assert str(settings.wellcome_catalogue_base_url) == (
        "https://api.wellcomecollection.org/catalogue/v2/"
    )
    assert settings.wellcome_user_agent == "HeritageRAG/0.1.0"
    assert settings.wellcome_connect_timeout_seconds == 5.0
    assert settings.wellcome_read_timeout_seconds == 30.0
    assert settings.wellcome_write_timeout_seconds == 30.0
    assert settings.wellcome_pool_timeout_seconds == 5.0
    assert settings.wellcome_max_attempts == 4
    assert settings.wellcome_max_retry_wait_seconds == 8.0
    assert settings.ingestion_state_directory == Path("var/ingestion")
    assert settings.bronze_data_directory == Path("data/bronze")
    assert settings.silver_data_directory == Path("data/silver")


def test_environment_variables_override_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Environment variables should override defaults with typed values."""

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv(
        "WELLCOME_CATALOGUE_BASE_URL",
        "https://example.test/catalogue/",
    )
    monkeypatch.setenv("WELLCOME_USER_AGENT", "HeritageRAG/test")
    monkeypatch.setenv("WELLCOME_CONNECT_TIMEOUT_SECONDS", "2.5")
    monkeypatch.setenv("WELLCOME_READ_TIMEOUT_SECONDS", "20")
    monkeypatch.setenv("WELLCOME_WRITE_TIMEOUT_SECONDS", "15")
    monkeypatch.setenv("WELLCOME_POOL_TIMEOUT_SECONDS", "3")
    monkeypatch.setenv("WELLCOME_MAX_ATTEMPTS", "2")
    monkeypatch.setenv("WELLCOME_MAX_RETRY_WAIT_SECONDS", "4.5")
    monkeypatch.setenv("INGESTION_STATE_DIRECTORY", "var/test-ingestion")
    monkeypatch.setenv("BRONZE_DATA_DIRECTORY", "data/test-bronze")
    monkeypatch.setenv("SILVER_DATA_DIRECTORY", "data/test-silver")

    settings = AppSettings(_env_file=None)

    assert settings.app_env is AppEnvironment.PRODUCTION
    assert settings.log_level is LogLevel.DEBUG
    assert str(settings.wellcome_catalogue_base_url) == (
        "https://example.test/catalogue/"
    )
    assert settings.wellcome_user_agent == "HeritageRAG/test"
    assert settings.wellcome_connect_timeout_seconds == 2.5
    assert settings.wellcome_read_timeout_seconds == 20.0
    assert settings.wellcome_write_timeout_seconds == 15.0
    assert settings.wellcome_pool_timeout_seconds == 3.0
    assert settings.wellcome_max_attempts == 2
    assert settings.wellcome_max_retry_wait_seconds == 4.5
    assert settings.ingestion_state_directory == Path("var/test-ingestion")
    assert settings.bronze_data_directory == Path("data/test-bronze")
    assert settings.silver_data_directory == Path("data/test-silver")


def test_invalid_environment_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unknown application environments should fail validation."""

    monkeypatch.setenv("APP_ENV", "staging")

    with pytest.raises(ValidationError):
        AppSettings(_env_file=None)


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("WELLCOME_CATALOGUE_BASE_URL", "ftp://example.test/catalogue/"),
        ("WELLCOME_USER_AGENT", ""),
        ("WELLCOME_CONNECT_TIMEOUT_SECONDS", "0"),
        ("WELLCOME_READ_TIMEOUT_SECONDS", "301"),
        ("WELLCOME_MAX_ATTEMPTS", "0"),
        ("WELLCOME_MAX_ATTEMPTS", "11"),
        ("WELLCOME_MAX_RETRY_WAIT_SECONDS", "0"),
        ("WELLCOME_MAX_RETRY_WAIT_SECONDS", "61"),
    ],
)
def test_invalid_wellcome_settings_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
    variable: str,
    value: str,
) -> None:
    """Unsafe Wellcome transport settings should fail validation."""

    monkeypatch.setenv(variable, value)

    with pytest.raises(ValidationError):
        AppSettings(_env_file=None)


def test_settings_provider_reuses_single_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The settings provider should return one instance per process."""

    monkeypatch.setenv("APP_ENV", "test")
    get_settings.cache_clear()

    try:
        first = get_settings()
        second = get_settings()

        assert first is second
        assert first.app_env is AppEnvironment.TEST
    finally:
        get_settings.cache_clear()


def test_settings_cannot_be_modified_after_creation() -> None:
    """Validated runtime settings should be immutable."""

    settings = AppSettings(_env_file=None)

    with pytest.raises(ValidationError):
        settings.log_level = LogLevel.DEBUG
