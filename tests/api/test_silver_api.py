"""Tests for read-only Silver dataset and page inspection endpoints."""

from pathlib import Path

from fastapi import status
from fastapi.testclient import TestClient

from european_heritage_rag.api.main import create_app
from european_heritage_rag.core.config import AppSettings, get_settings
from european_heritage_rag.domain.silver import (
    OcrQualityBand,
    PageQualityFlag,
    SilverLineage,
    SilverPage,
    SilverQualityReport,
    SilverWork,
    WorkQualitySummary,
)
from european_heritage_rag.pipeline.bronze import BronzeResourceType
from european_heritage_rag.pipeline.silver import SilverTransformResult
from european_heritage_rag.pipeline.silver_store import SilverFilesystemStore

_DATASET_ID = "a" * 64
_CONTENT_HASH = "b" * 64


def create_silver_fixture(root: Path) -> str:
    """Publish one complete work/page dataset for API tests."""

    catalogue_lineage = SilverLineage(
        resource_id="catalogue_work:work-1",
        resource_type=BronzeResourceType.CATALOGUE_WORK,
        relative_path="works/work-1/work.json",
        source_url="https://example.test/catalogue",
        content_sha256=_CONTENT_HASH,
    )
    manifest_lineage = SilverLineage(
        resource_id="iiif_manifest:work-1",
        resource_type=BronzeResourceType.IIIF_MANIFEST,
        relative_path="works/work-1/manifest.json",
        source_url="https://example.test/manifest",
        content_sha256="c" * 64,
    )
    work = SilverWork(
        dataset_id=_DATASET_ID,
        work_id="work-1",
        title="Fixture work",
        language_ids=("eng",),
        language_labels=("English",),
        licence_id="pdm",
        source_url="https://wellcomecollection.org/works/work-1",
        iiif_manifest_url="https://example.test/manifest",
        source_content_sha256=_CONTENT_HASH,
        iiif_manifest_content_sha256="c" * 64,
        lineage=(catalogue_lineage, manifest_lineage),
    )
    page = SilverPage(
        dataset_id=_DATASET_ID,
        page_id="d" * 64,
        work_id="work-1",
        canvas_id="https://example.test/canvas/1",
        sequence_number=1,
        page_label="-",
        raw_text="",
        clean_text="",
        ocr_quality=OcrQualityBand.MISSING,
        quality_flags=(
            PageQualityFlag.EMPTY_OCR,
            PageQualityFlag.MISSING_PAGE_LABEL,
        ),
        raw_line_count=0,
        raw_word_count=0,
        clean_word_count=0,
        cleaning_change_ratio=0,
        lineage=(manifest_lineage,),
    )
    quality = SilverQualityReport(
        dataset_id=_DATASET_ID,
        work_count=1,
        page_count=1,
        empty_page_count=1,
        review_page_count=0,
        usable_page_count=0,
        average_clean_word_count=0,
        language_counts={"eng": 1},
        page_flag_counts={"empty_ocr": 1, "missing_page_label": 1},
        works=(
            WorkQualitySummary(
                work_id="work-1",
                page_count=1,
                empty_page_count=1,
                review_page_count=0,
                average_clean_word_count=0,
            ),
        ),
    )
    SilverFilesystemStore(root).publish(
        SilverTransformResult(
            dataset_id=_DATASET_ID,
            bronze_run_id="bronze-run",
            bronze_inventory_sha256="e" * 64,
            works=(work,),
            pages=(page,),
            quality_report=quality,
        ),
        pipeline_version="test",
    )
    return page.page_id


def test_silver_endpoints_list_filter_and_show_page(tmp_path: Path) -> None:
    """API should expose bounded lists and full selected page detail."""

    silver_root = tmp_path / "silver"
    page_id = create_silver_fixture(silver_root)
    settings = AppSettings(
        _env_file=None,
        app_env="test",
        silver_data_directory=silver_root,
    )
    application = create_app(tmp_path / "missing-frontend")
    application.dependency_overrides[get_settings] = lambda: settings

    with TestClient(application) as client:
        datasets = client.get("/silver/datasets")
        works = client.get(f"/silver/datasets/{_DATASET_ID}/works")
        pages = client.get(
            f"/silver/datasets/{_DATASET_ID}/pages",
            params={"quality_flag": "empty_ocr"},
        )
        detail = client.get(f"/silver/datasets/{_DATASET_ID}/pages/{page_id}")
        quality = client.get(f"/silver/datasets/{_DATASET_ID}/quality")

    assert datasets.status_code == status.HTTP_200_OK
    assert datasets.json()[0]["dataset_id"] == _DATASET_ID
    assert works.json()[0]["title"] == "Fixture work"
    assert pages.json()["total"] == 1
    assert "raw_text" not in pages.json()["items"][0]
    assert detail.json()["quality_flags"] == [
        "empty_ocr",
        "missing_page_label",
    ]
    assert quality.json()["empty_page_count"] == 1


def test_silver_endpoints_return_not_found(tmp_path: Path) -> None:
    """Unknown logical IDs should return normal not-found responses."""

    settings = AppSettings(
        _env_file=None,
        app_env="test",
        silver_data_directory=tmp_path / "silver",
    )
    application = create_app(tmp_path / "missing-frontend")
    application.dependency_overrides[get_settings] = lambda: settings

    with TestClient(application) as client:
        missing = client.get("/silver/datasets/missing")

    assert missing.status_code == status.HTTP_404_NOT_FOUND
