"""Tests for read-only Bronze inspection endpoints."""

from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import quote

from fastapi import status
from fastapi.testclient import TestClient

from european_heritage_rag.api.main import create_app
from european_heritage_rag.core.config import AppSettings, get_settings
from european_heritage_rag.pipeline.bronze import (
    BronzeResourceIdentity,
    BronzeResourceType,
    BronzeRunIdentity,
    BronzeRunManifest,
    BronzeRunStatus,
    WellcomeBronzeParameters,
)
from european_heritage_rag.pipeline.bronze_store import BronzeFilesystemStore

NOW = datetime(2026, 7, 23, 9, 0, tzinfo=UTC)


def create_bronze_fixture(
    root: Path,
) -> tuple[BronzeRunManifest, str]:
    """Create one inspectable run and raw work resource."""

    store = BronzeFilesystemStore(root)
    run = BronzeRunIdentity(
        ingestion_date=date(2026, 7, 23),
        run_id="api-run",
    )
    identity = BronzeResourceIdentity(
        resource_type=BronzeResourceType.CATALOGUE_WORK,
        work_id="xpxuaxuf",
        source_url="https://example.test/catalogue/works",
    )
    result = store.write_resource(
        run=run,
        resource=identity,
        content=b'{"id":"xpxuaxuf","title":"Raw fixture work"}',
        acquired_at=NOW,
        content_type="application/json",
    )
    manifest = BronzeRunManifest(
        identity=run,
        status=BronzeRunStatus.RUNNING,
        pipeline_version="0.1.0",
        parameters=WellcomeBronzeParameters(limit=1),
        catalogue_base_url=("https://api.wellcomecollection.org/catalogue/v2/"),
        started_at=NOW,
        updated_at=NOW,
        requested_work_count=1,
        discovered_work_count=1,
        completed_work_count=0,
        resources=(result.record,),
    )
    store.write_manifest(manifest)
    return manifest, result.record.resource_id


def test_bronze_endpoints_list_detail_and_raw_resource(
    tmp_path: Path,
) -> None:
    """The browser contract should expose manifests and declared JSON only."""

    bronze_root = tmp_path / "bronze"
    manifest, resource_id = create_bronze_fixture(bronze_root)
    settings = AppSettings(
        _env_file=None,
        app_env="test",
        bronze_data_directory=bronze_root,
    )
    application = create_app(tmp_path / "missing-frontend")
    application.dependency_overrides[get_settings] = lambda: settings

    with TestClient(application) as client:
        runs_response = client.get("/bronze/runs")
        detail_response = client.get(f"/bronze/runs/{manifest.identity.run_id}")
        resource_response = client.get(
            "/bronze/runs/"
            f"{manifest.identity.run_id}/resources/"
            f"{quote(resource_id, safe='')}"
        )

    assert runs_response.status_code == status.HTTP_200_OK
    assert runs_response.json()[0]["identity"]["run_id"] == "api-run"
    assert detail_response.status_code == status.HTTP_200_OK
    assert detail_response.json()["resources"][0]["resource_id"] == resource_id
    assert resource_response.status_code == status.HTTP_200_OK
    assert resource_response.json()["title"] == "Raw fixture work"


def test_bronze_endpoints_return_not_found_for_unknown_ids(
    tmp_path: Path,
) -> None:
    """Unknown run and resource identities should not expose filesystem paths."""

    bronze_root = tmp_path / "bronze"
    manifest, _ = create_bronze_fixture(bronze_root)
    settings = AppSettings(
        _env_file=None,
        app_env="test",
        bronze_data_directory=bronze_root,
    )
    application = create_app(tmp_path / "missing-frontend")
    application.dependency_overrides[get_settings] = lambda: settings

    with TestClient(application) as client:
        missing_run = client.get("/bronze/runs/missing")
        missing_resource = client.get(
            f"/bronze/runs/{manifest.identity.run_id}/resources/missing"
        )

    assert missing_run.status_code == status.HTTP_404_NOT_FOUND
    assert missing_resource.status_code == status.HTTP_404_NOT_FOUND
