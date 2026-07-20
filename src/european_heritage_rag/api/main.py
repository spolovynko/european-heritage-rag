"""FastAPI application entry point for HeritageRAG."""

from importlib.metadata import version

from fastapi import FastAPI

_APPLICATION_TITLE = "HeritageRAG"
_DISTRIBUTION_NAME = "european-heritage-rag"


def create_app() -> FastAPI:
    """Construct and configure the HeritageRAG API."""

    return FastAPI(
        title=_APPLICATION_TITLE,
        version=version(_DISTRIBUTION_NAME),
    )


app = create_app()
