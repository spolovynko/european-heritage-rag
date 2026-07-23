"""Tests for Silver Parquet publication and validation."""

from pathlib import Path

from test_silver_transform import create_bronze_run

from european_heritage_rag.pipeline.silver import transform_bronze_run
from european_heritage_rag.pipeline.silver_store import (
    SilverFilesystemStore,
    validate_silver_dataset,
)


def test_publish_round_trips_parquet_and_reuses_complete_dataset(
    tmp_path: Path,
) -> None:
    """A complete dataset should validate and be idempotently reused."""

    bronze_store, bronze_manifest = create_bronze_run(tmp_path)
    transformed = transform_bronze_run(
        bronze_store,
        bronze_manifest,
    )
    silver_store = SilverFilesystemStore(tmp_path / "silver")

    first = silver_store.publish(transformed, pipeline_version="test")
    second = silver_store.publish(transformed, pipeline_version="test")

    assert first.created is True
    assert second.created is False
    assert first.manifest == second.manifest
    assert len(silver_store.read_works(transformed.dataset_id)) == 1
    assert len(silver_store.read_pages(transformed.dataset_id)) == 2
    assert validate_silver_dataset(silver_store, first.manifest).is_valid


def test_changed_parquet_is_reported(tmp_path: Path) -> None:
    """A completed dataset should expose local corruption."""

    bronze_store, bronze_manifest = create_bronze_run(tmp_path)
    transformed = transform_bronze_run(
        bronze_store,
        bronze_manifest,
    )
    silver_store = SilverFilesystemStore(tmp_path / "silver")
    published = silver_store.publish(transformed, pipeline_version="test")
    pages_path = (
        silver_store.dataset_directory(transformed.dataset_id) / "pages.parquet"
    )
    pages_path.write_bytes(pages_path.read_bytes() + b"changed")

    report = validate_silver_dataset(silver_store, published.manifest)

    assert not report.is_valid
    assert {issue.code for issue in report.issues} >= {
        "byte_length_mismatch",
        "content_hash_mismatch",
    }
