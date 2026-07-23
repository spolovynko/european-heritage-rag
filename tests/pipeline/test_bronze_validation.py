"""Tests for offline Bronze integrity and replay validation."""

import json
from datetime import UTC, date, datetime
from pathlib import Path

from european_heritage_rag.pipeline.bronze import (
    BronzeResourceIdentity,
    BronzeResourceType,
    BronzeRunIdentity,
    BronzeRunManifest,
    BronzeRunStatus,
    WellcomeBronzeParameters,
)
from european_heritage_rag.pipeline.bronze_store import BronzeFilesystemStore
from european_heritage_rag.pipeline.bronze_validation import validate_bronze_run

FIXTURE_DIRECTORY = Path(__file__).parents[1] / "fixtures" / "wellcome"
STARTED_AT = datetime(2026, 7, 23, 9, 0, tzinfo=UTC)


def fixture_bytes(filename: str) -> bytes:
    """Read one committed Wellcome fixture as exact bytes."""

    return (FIXTURE_DIRECTORY / filename).read_bytes()


def create_valid_run(
    tmp_path: Path,
) -> tuple[BronzeFilesystemStore, BronzeRunManifest]:
    """Create a complete fixture run with one work and one annotation."""

    store = BronzeFilesystemStore(tmp_path / "bronze")
    run = BronzeRunIdentity(
        ingestion_date=date(2026, 7, 23),
        run_id="validation-run",
    )
    catalogue_page = json.loads(fixture_bytes("catalogue_page.json"))
    work_content = json.dumps(
        catalogue_page["results"][0],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()
    inputs = (
        (
            BronzeResourceIdentity(
                resource_type=BronzeResourceType.CATALOGUE_WORK,
                work_id="xpxuaxuf",
                source_url="https://example.test/catalogue/works",
            ),
            work_content,
        ),
        (
            BronzeResourceIdentity(
                resource_type=BronzeResourceType.IIIF_MANIFEST,
                work_id="xpxuaxuf",
                source_url="https://iiif.example.org/manifests/a2222",
            ),
            fixture_bytes("iiif_manifest.json"),
        ),
        (
            BronzeResourceIdentity(
                resource_type=BronzeResourceType.OCR_ANNOTATION_LIST,
                work_id="xpxuaxuf",
                source_url="https://iiif.example.org/annotations/page-1",
                canvas_index=0,
                annotation_index=0,
            ),
            fixture_bytes("ocr_annotation_list.json"),
        ),
    )
    records = tuple(
        store.write_resource(
            run=run,
            resource=identity,
            content=content,
            acquired_at=STARTED_AT,
            content_type="application/json",
        ).record
        for identity, content in inputs
    )
    manifest = BronzeRunManifest(
        identity=run,
        status=BronzeRunStatus.COMPLETED,
        pipeline_version="0.1.0",
        parameters=WellcomeBronzeParameters(limit=1, query="cholera"),
        catalogue_base_url=("https://api.wellcomecollection.org/catalogue/v2/"),
        started_at=STARTED_AT,
        updated_at=STARTED_AT,
        finished_at=STARTED_AT,
        requested_work_count=1,
        discovered_work_count=1,
        completed_work_count=1,
        completed_work_ids=("xpxuaxuf",),
        canvas_count=1,
        annotation_count=1,
        resources=records,
    )
    store.write_manifest(manifest)
    return store, manifest


def test_valid_run_replays_without_network(tmp_path: Path) -> None:
    """Valid source payloads should parse entirely from Bronze files."""

    store, manifest = create_valid_run(tmp_path)

    report = validate_bronze_run(store, manifest)

    assert report.is_valid
    assert report.checked_resource_count == 3
    assert report.issues == ()


def test_changed_resource_is_reported(tmp_path: Path) -> None:
    """Changed bytes must fail the recorded length and hash checks."""

    store, manifest = create_valid_run(tmp_path)
    record = manifest.resources[0]
    path = store.run_directory(manifest.identity).joinpath(
        *Path(record.relative_path).parts
    )
    path.write_bytes(b'{"changed":true}')

    report = validate_bronze_run(store, manifest)
    issue_codes = {issue.code for issue in report.issues}

    assert not report.is_valid
    assert "byte_length_mismatch" in issue_codes
    assert "content_hash_mismatch" in issue_codes
    assert "invalid_source_shape" in issue_codes


def test_missing_and_unlisted_resources_are_reported(tmp_path: Path) -> None:
    """The validator should compare the ledger with the actual run tree."""

    store, manifest = create_valid_run(tmp_path)
    declared = manifest.resources[-1]
    declared_path = store.run_directory(manifest.identity).joinpath(
        *Path(declared.relative_path).parts
    )
    declared_path.unlink()
    unlisted_path = store.run_directory(manifest.identity) / "orphan.json"
    unlisted_path.write_text('{"orphan":true}', encoding="utf-8")

    report = validate_bronze_run(store, manifest)
    issue_codes = {issue.code for issue in report.issues}

    assert "missing_resource" in issue_codes
    assert "unlisted_resource" in issue_codes
