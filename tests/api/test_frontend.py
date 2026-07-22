"""Tests for serving the built frontend through FastAPI."""

from pathlib import Path

from fastapi import status
from fastapi.testclient import TestClient

from european_heritage_rag.api.main import create_app


def test_frontend_and_api_routes_are_served_together(tmp_path: Path) -> None:
    """The root mount should serve UI assets without hiding API routes."""

    (tmp_path / "index.html").write_text(
        '<!doctype html><script src="/assets/app.js"></script>',
        encoding="utf-8",
    )
    assets_directory = tmp_path / "assets"
    assets_directory.mkdir()
    (assets_directory / "app.js").write_text(
        'document.title = "HeritageRAG";',
        encoding="utf-8",
    )

    with TestClient(create_app(frontend_directory=tmp_path)) as client:
        frontend_response = client.get("/")
        asset_response = client.get("/assets/app.js")
        readiness_response = client.get("/health/ready")

    assert frontend_response.status_code == status.HTTP_200_OK
    assert frontend_response.headers["content-type"].startswith("text/html")
    assert asset_response.status_code == status.HTTP_200_OK
    assert "HeritageRAG" in asset_response.text
    assert readiness_response.status_code == status.HTTP_200_OK


def test_missing_frontend_directory_does_not_prevent_api_startup(
    tmp_path: Path,
) -> None:
    """API routes should remain available before frontend assets are built."""

    missing_directory = tmp_path / "missing"

    with TestClient(create_app(frontend_directory=missing_directory)) as client:
        frontend_response = client.get("/")
        liveness_response = client.get("/health/live")

    assert frontend_response.status_code == status.HTTP_404_NOT_FOUND
    assert liveness_response.status_code == status.HTTP_200_OK
