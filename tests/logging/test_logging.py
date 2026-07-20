"""Tests for structured logging configuration."""

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