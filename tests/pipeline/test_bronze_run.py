"""Tests for resumable Bronze run-ledger coordination."""

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from european_heritage_rag.pipeline.bronze import (
    BronzeResourceIdentity,
    BronzeResourceType,
    BronzeRunIdentity,
    BronzeRunStatus,
    WellcomeBronzeParameters,
)
from european_heritage_rag.pipeline.bronze_run import BronzeRunRecorder
from european_heritage_rag.pipeline.bronze_store import BronzeFilesystemStore

STARTED_AT = datetime(2026, 7, 23, 9, 0, tzinfo=UTC)


def start_recorder(tmp_path: Path) -> BronzeRunRecorder:
    """Start one fixture recorder."""

    return BronzeRunRecorder.start(
        BronzeFilesystemStore(tmp_path / "bronze"),
        identity=BronzeRunIdentity(
            ingestion_date=date(2026, 7, 23),
            run_id="ledger-run",
        ),
        parameters=WellcomeBronzeParameters(limit=1, query="cholera"),
        catalogue_base_url=("https://api.wellcomecollection.org/catalogue/v2/"),
        pipeline_version="0.1.0",
        started_at=STARTED_AT,
        now=STARTED_AT,
        resume=False,
    )


def record_required_work_resources(
    recorder: BronzeRunRecorder,
) -> None:
    """Write the two raw resources required before completing a work."""

    for resource_type, filename in (
        (BronzeResourceType.CATALOGUE_WORK, "work"),
        (BronzeResourceType.IIIF_MANIFEST, "manifest"),
    ):
        recorder.record_resource(
            resource=BronzeResourceIdentity(
                resource_type=resource_type,
                work_id="xpxuaxuf",
                source_url=f"https://example.test/{filename}.json",
            ),
            content=f'{{"resource":"{filename}"}}'.encode(),
            acquired_at=STARTED_AT,
            content_type="application/json",
            now=STARTED_AT,
        )


def test_resource_receipt_is_committed_immediately(tmp_path: Path) -> None:
    """A successful raw write should be visible in the persisted ledger."""

    recorder = start_recorder(tmp_path)
    recorder.record_resource(
        resource=BronzeResourceIdentity(
            resource_type=BronzeResourceType.CATALOGUE_WORK,
            work_id="xpxuaxuf",
            source_url="https://example.test/work.json",
        ),
        content=b'{"id":"xpxuaxuf"}',
        acquired_at=STARTED_AT,
        content_type="application/json",
        now=STARTED_AT,
    )

    store = BronzeFilesystemStore(tmp_path / "bronze")
    persisted = store.load_manifest(recorder.manifest.identity)

    assert persisted is not None
    assert len(persisted.resources) == 1


def test_success_resolves_failure_without_erasing_history(
    tmp_path: Path,
) -> None:
    """A retry should retain and resolve the earlier failed-URL record."""

    recorder = start_recorder(tmp_path)
    recorder.record_discovery(1, now=STARTED_AT)
    recorder.record_failure(
        work_id="xpxuaxuf",
        resource_type=BronzeResourceType.IIIF_MANIFEST,
        source_url="https://example.test/manifest.json",
        error=OSError("temporary source failure"),
        now=STARTED_AT,
    )
    record_required_work_resources(recorder)
    completed_at = STARTED_AT + timedelta(minutes=1)
    recorder.record_work_success(
        "xpxuaxuf",
        canvas_count=2,
        missing_ocr_page_count=1,
        now=completed_at,
    )
    manifest = recorder.finish(
        BronzeRunStatus.COMPLETED,
        now=completed_at,
    )

    assert manifest.completed_work_ids == ("xpxuaxuf",)
    assert manifest.canvas_count == 2
    assert manifest.missing_ocr_page_count == 1
    assert len(manifest.failures) == 1
    assert manifest.failures[0].resolved_at == completed_at


def test_resume_reopens_same_ledger_and_preserves_resources(
    tmp_path: Path,
) -> None:
    """A matching resume should reuse the same run and inventory."""

    recorder = start_recorder(tmp_path)
    recorder.record_resource(
        resource=BronzeResourceIdentity(
            resource_type=BronzeResourceType.CATALOGUE_WORK,
            work_id="xpxuaxuf",
            source_url="https://example.test/work.json",
        ),
        content=b'{"id":"xpxuaxuf"}',
        acquired_at=STARTED_AT,
        content_type="application/json",
        now=STARTED_AT,
    )
    resumed_at = STARTED_AT + timedelta(minutes=5)
    store = BronzeFilesystemStore(tmp_path / "bronze")

    resumed = BronzeRunRecorder.start(
        store,
        identity=recorder.manifest.identity,
        parameters=recorder.manifest.parameters,
        catalogue_base_url=str(recorder.manifest.catalogue_base_url),
        pipeline_version="0.1.0",
        started_at=STARTED_AT,
        now=resumed_at,
        resume=True,
    )

    assert resumed.manifest.status is BronzeRunStatus.RUNNING
    assert resumed.manifest.finished_at is None
    assert resumed.manifest.resources == recorder.manifest.resources
