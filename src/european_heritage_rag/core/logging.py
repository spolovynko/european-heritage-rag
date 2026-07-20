"""Structured logging configuration and logger factory for HeritageRAG."""

import logging
import sys

import structlog
from structlog.typing import Processor

from european_heritage_rag.core.config import (
    AppEnvironment,
    AppSettings,
)


def configure_logging(settings: AppSettings) -> None:
    """Configure standard-library logging and Structlog."""

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    renderer: Processor
    if settings.app_env is AppEnvironment.PRODUCTION:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=False)

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(settings.log_level.value)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=False,
    )


def get_logger(
    name: str,
    **initial_context: object,
) -> structlog.stdlib.BoundLogger:
    """Return a named structured logger with optional initial context."""

    return structlog.stdlib.get_logger(name, **initial_context)
