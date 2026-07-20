"""Tests for application configuration."""

import pytest

from european_heritage_rag.core.config import (
    AppEnvironment,
    AppSettings,
    LogLevel,
)


def test_settings_use_safe_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings should use documented defaults without external configuration."""

    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)

    settings = AppSettings(_env_file=None)

    assert settings.app_env is AppEnvironment.LOCAL
    assert settings.log_level is LogLevel.INFO