"""Tests for the file-backed ingestion status endpoint."""

from datetime import UTC, datetime
from pathlib import Path

from fastapi import status
from fastapi.testclient import TestClient

from european_heritage_rag.api.main import create_app
from european_heritage_rag.core.config import AppSettings, get_settings
from european_heritage_rag.sources.wellcome.ingestion import (
    IngestionEvent,
    IngestionStateStore,
    IngestionStatus,
)


def test_ingestion_status_is_idle_before_first_run(tmp_path: Path) -> None:
    settings = AppSettings(
        _env_file=None,
        ingestion_state_directory=tmp_path / "state",
    )
    application = create_app(frontend_directory=tmp_path / "missing-frontend")
    application.dependency_overrides[get_settings] = lambda: settings

    with TestClient(application) as client:
        response = client.get("/ingestion/status")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "idle"
    assert response.json()["works_discovered"] == 0
    assert response.json()["recent_events"] == []


def test_ingestion_status_returns_latest_saved_progress(tmp_path: Path) -> None:
    state_directory = tmp_path / "state"
    settings = AppSettings(
        _env_file=None,
        ingestion_state_directory=state_directory,
    )
    event_time = datetime.now(UTC)
    IngestionStateStore(state_directory).save_status(
        IngestionStatus(
            status="running",
            run_id="test-run",
            requested_limit=5,
            current_work_id="xpxuaxuf",
            current_work_title="Cholera",
            works_discovered=5,
            works_completed=2,
            pages_downloaded=24,
            retry_count=1,
            recent_events=[
                IngestionEvent(
                    timestamp=event_time,
                    level="info",
                    message="Traversing Cholera",
                    work_id="xpxuaxuf",
                )
            ],
            started_at=event_time,
            updated_at=event_time,
        )
    )
    application = create_app(frontend_directory=tmp_path / "missing-frontend")
    application.dependency_overrides[get_settings] = lambda: settings

    with TestClient(application) as client:
        response = client.get("/ingestion/status")

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["run_id"] == "test-run"
    assert payload["current_work_id"] == "xpxuaxuf"
    assert payload["works_completed"] == 2
    assert payload["pages_downloaded"] == 24
    assert payload["retry_count"] == 1
    assert payload["recent_events"][0]["message"] == "Traversing Cholera"
