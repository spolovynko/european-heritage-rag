"""FastAPI application entry point for HeritageRAG."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import version
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, status
from fastapi.staticfiles import StaticFiles

from european_heritage_rag.api.contracts import HealthResponse, ReadinessResponse
from european_heritage_rag.core.config import AppSettings, get_settings
from european_heritage_rag.core.logging import configure_logging, get_logger

_APPLICATION_TITLE = "HeritageRAG"
_DISTRIBUTION_NAME = "european-heritage-rag"
_APPLICATION_VERSION = version(_DISTRIBUTION_NAME)
_DEFAULT_FRONTEND_DIRECTORY = Path("frontend/dist")


def get_liveness() -> HealthResponse:
    """Return the liveness status of the HeritageRAG API."""
    return HealthResponse(
        status="ok",
        service=_APPLICATION_TITLE,
        version=_APPLICATION_VERSION,
    )


async def get_readiness(
    _settings: Annotated[AppSettings, Depends(get_settings)],
) -> ReadinessResponse:
    """Report whether the API can serve its current workload."""

    return ReadinessResponse(
        status="ok",
        service=_APPLICATION_TITLE,
        version=_APPLICATION_VERSION,
        checks={"configuration": "ok"},
    )


logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings)

    logger.info(
        "application_started",
        environment=settings.app_env.value,
        version=_APPLICATION_VERSION,
    )

    try:
        yield
    finally:
        logger.info("application_stopped")


def create_app(
    frontend_directory: Path = _DEFAULT_FRONTEND_DIRECTORY,
) -> FastAPI:
    """Construct and configure the HeritageRAG API."""

    application = FastAPI(
        title=_APPLICATION_TITLE,
        version=_APPLICATION_VERSION,
        lifespan=lifespan,
    )

    application.add_api_route(
        path="/health/live",
        endpoint=get_liveness,
        methods=["GET"],
        response_model=HealthResponse,
        status_code=status.HTTP_200_OK,
        summary="Get the liveness status of the HeritageRAG API.",
    )

    application.add_api_route(
        path="/health/ready",
        endpoint=get_readiness,
        methods=["GET"],
        response_model=ReadinessResponse,
        status_code=status.HTTP_200_OK,
        tags=["health"],
        summary="Check API readiness",
    )

    if frontend_directory.is_dir():
        application.mount(
            path="/",
            app=StaticFiles(directory=frontend_directory, html=True),
            name="frontend",
        )

    return application


app = create_app()
