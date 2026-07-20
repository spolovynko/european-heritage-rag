"""Tests for application configuration."""

import pytest
from pydantic import ValidationError

from european_heritage_rag.core.config import (
    AppEnvironment,
    AppSettings,
    LogLevel,
    get_settings,
)


def test_settings_use_safe_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings should use documented defaults without external configuration."""

    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)

    settings = AppSettings(_env_file=None)

    assert settings.app_env is AppEnvironment.LOCAL
    assert settings.log_level is LogLevel.INFO


def test_environment_variables_override_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Environment variables should override defaults with typed values."""

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    settings = AppSettings(_env_file=None)

    assert settings.app_env is AppEnvironment.PRODUCTION
    assert settings.log_level is LogLevel.DEBUG


def test_invalid_environment_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unknown application environments should fail validation."""

    monkeypatch.setenv("APP_ENV", "staging")

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
