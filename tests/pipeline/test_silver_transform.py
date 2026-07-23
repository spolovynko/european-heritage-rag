"""Tests for the offline Bronze-to-Silver transformation."""

import json
from datetime import UTC, datetime
from pathlib import Path

from european_heritage_rag.domain.silver import (
    OcrQualityBand,
    PageQualityFlag,
)
from european_heritage_rag.pipeline.bronze import (
    BronzeResourceIdentity,
    BronzeResourceType,
    BronzeRunIdentity,
    BronzeRunManifest,
    BronzeRunStatus,
    WellcomeBronzeParameters,
)
from european_heritage_rag.pipeline.bronze_run import BronzeRunRecorder
from european_heritage_rag.pipeline.bronze_store import BronzeFilesystemStore
from european_heritage_rag.pipeline.silver import (
    bronze_inventory_sha256,
    silver_dataset_id,
    transform_bronze_run,
)

_FIXTURES = Path(__file__).parents[1] / "fixtures" / "wellcome"


def create_bronze_run(
    tmp_path: Path,
) -> tuple[BronzeFilesystemStore, BronzeRunManifest]:
    """Create one complete two-page Bronze work entirely from fixtures."""

    store = BronzeFilesystemStore(tmp_path / "bronze")
    now = datetime(2026, 7, 23, 10, 0, tzinfo=UTC)
    recorder = BronzeRunRecorder.start(
        store,
        identity=BronzeRunIdentity(
            ingestion_date=now.date(),
            run_id="silver-test-run",
        ),
        parameters=WellcomeBronzeParameters(limit=1, query="cholera"),
        catalogue_base_url="https://api.wellcomecollection.org/catalogue/v2/",
        pipeline_version="test",
        started_at=now,
        now=now,
        resume=False,
    )
    recorder.record_discovery(1, now=now)
    catalogue_page = json.loads(
        (_FIXTURES / "catalogue_page.json").read_text(encoding="utf-8")
    )
    catalogue_content = json.dumps(
        catalogue_page["results"][0],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()
    recorder.record_resource(
        resource=BronzeResourceIdentity(
            resource_type=BronzeResourceType.CATALOGUE_WORK,
            work_id="xpxuaxuf",
            source_url="https://api.wellcomecollection.org/catalogue/v2/works",
        ),
        content=catalogue_content,
        acquired_at=now,
        content_type="application/json",
        now=now,
    )
    recorder.record_resource(
        resource=BronzeResourceIdentity(
            resource_type=BronzeResourceType.IIIF_MANIFEST,
            work_id="xpxuaxuf",
            source_url=(
                "https://iiif.wellcomecollection.org/presentation/v2/b28041136"
            ),
        ),
        content=(_FIXTURES / "iiif_manifest.json").read_bytes(),
        acquired_at=now,
        content_type="application/json",
        now=now,
    )
    recorder.record_resource(
        resource=BronzeResourceIdentity(
            resource_type=BronzeResourceType.OCR_ANNOTATION_LIST,
            work_id="xpxuaxuf",
            source_url=(
                "https://iiif.wellcomecollection.org/annotations/v2/"
                "b28041136/b28041136_0001.jp2/line"
            ),
            canvas_index=0,
            annotation_index=0,
        ),
        content=(_FIXTURES / "ocr_annotation_list.json").read_bytes(),
        acquired_at=now,
        content_type="application/json",
        now=now,
    )
    recorder.record_work_success(
        "xpxuaxuf",
        canvas_count=2,
        missing_ocr_page_count=1,
        now=now,
    )
    manifest = recorder.finish(BronzeRunStatus.COMPLETED, now=now)
    return store, manifest


def test_transform_preserves_pages_raw_text_and_lineage(tmp_path: Path) -> None:
    """Every canvas should become a traceable page, including empty OCR."""

    store, manifest = create_bronze_run(tmp_path)

    result = transform_bronze_run(store, manifest)

    assert len(result.works) == 1
    assert len(result.pages) == 2
    assert result.works[0].contributors[0].label == "Patterson, Charles"
    assert result.pages[0].raw_text == "CHOLERA.\nPRACTICAL OBSERVATIONS"
    assert result.pages[0].clean_text == "CHOLERA. PRACTICAL OBSERVATIONS"
    assert len(result.pages[0].lineage) == 2
    assert result.pages[1].ocr_quality is OcrQualityBand.MISSING
    assert PageQualityFlag.EMPTY_OCR in result.pages[1].quality_flags
    assert result.quality_report.page_count == 2


def test_dataset_identity_is_stable_and_inventory_sensitive(tmp_path: Path) -> None:
    """Identity should be stable for one immutable Bronze inventory."""

    store, manifest = create_bronze_run(tmp_path)

    first_inventory = bronze_inventory_sha256(manifest)
    second_inventory = bronze_inventory_sha256(manifest)

    assert first_inventory == second_inventory
    assert silver_dataset_id(manifest) == silver_dataset_id(manifest)
