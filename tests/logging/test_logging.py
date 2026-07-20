"""Tests for structured logging configuration."""

import json
import logging
from collections.abc import Iterator

import pytest
import structlog

from european_heritage_rag.core.config import (
    AppEnvironment,
    AppSettings,
    LogLevel,
)
from european_heritage_rag.core.logging import (
    configure_logging,
    get_logger,
)


@pytest.fixture
def restore_logging_state() -> Iterator[None]:
    """Restore process-wide logging state after each test."""

    root_logger = logging.getLogger()
    original_handlers = root_logger.handlers.copy()
    original_level = root_logger.level

    try:
        yield
    finally:
        root_logger.handlers.clear()
        root_logger.handlers.extend(original_handlers)
        root_logger.setLevel(original_level)
        structlog.reset_defaults()


def test_local_logging_uses_readable_structured_output(
    capsys: pytest.CaptureFixture[str],
    restore_logging_state: None,
) -> None:
    """Local logs should be readable while retaining structured fields."""

    settings = AppSettings(
        _env_file=None,
        app_env=AppEnvironment.LOCAL,
        log_level=LogLevel.INFO,
    )
    configure_logging(settings)

    logger = get_logger(__name__)
    logger.info("logging_ready", component="phase_2")

    output = capsys.readouterr().out

    assert "logging_ready" in output
    assert "component=phase_2" in output
    assert __name__ in output
    assert "info" in output


def test_production_logging_uses_json_output(
    capsys: pytest.CaptureFixture[str],
    restore_logging_state: None,
) -> None:
    """Production logs should be machine-readable JSON."""

    settings = AppSettings(
        _env_file=None,
        app_env=AppEnvironment.PRODUCTION,
        log_level=LogLevel.INFO,
    )
    configure_logging(settings)

    logger = get_logger(__name__, component="api")
    logger.info("application_started", version="0.1.0")

    output = capsys.readouterr().out
    event = json.loads(output)

    assert event["event"] == "application_started"
    assert event["component"] == "api"
    assert event["version"] == "0.1.0"
    assert event["logger"] == __name__
    assert event["level"] == "info"
    assert "timestamp" in event


def test_logging_filters_events_below_configured_level(
    capsys: pytest.CaptureFixture[str],
    restore_logging_state: None,
) -> None:
    """Events below the configured level should not be emitted."""

    settings = AppSettings(
        _env_file=None,
        app_env=AppEnvironment.LOCAL,
        log_level=LogLevel.INFO,
    )
    configure_logging(settings)

    logger = get_logger(__name__)
    logger.debug("debug_event")
    logger.info("info_event")

    output = capsys.readouterr().out

    assert "debug_event" not in output
    assert "info_event" in output


def test_standard_library_logs_use_configured_renderer(
    capsys: pytest.CaptureFixture[str],
    restore_logging_state: None,
) -> None:
    """Third-party standard-library logs should use the production format."""

    settings = AppSettings(
        _env_file=None,
        app_env=AppEnvironment.PRODUCTION,
        log_level=LogLevel.INFO,
    )
    configure_logging(settings)

    standard_logger = logging.getLogger("third_party")
    standard_logger.info("library_ready")

    output = capsys.readouterr().out
    event = json.loads(output)

    assert event["event"] == "library_ready"
    assert event["logger"] == "third_party"
    assert event["level"] == "info"
    assert "timestamp" in event
