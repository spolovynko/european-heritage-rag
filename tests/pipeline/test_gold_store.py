"""Tests for deterministic Gold transformation and publication."""

from pathlib import Path

from gold_test_support import WhitespaceTokenizer
from test_silver_transform import create_bronze_run

from european_heritage_rag.domain.gold import GoldScope
from european_heritage_rag.pipeline.chunking import chunking_profiles
from european_heritage_rag.pipeline.gold import transform_silver_dataset
from european_heritage_rag.pipeline.gold_store import (
    GoldFilesystemStore,
    validate_gold_dataset,
)
from european_heritage_rag.pipeline.silver import transform_bronze_run
from european_heritage_rag.pipeline.silver_store import SilverFilesystemStore


def _create_silver(tmp_path: Path) -> tuple[SilverFilesystemStore, str]:
    bronze_store, bronze_manifest = create_bronze_run(tmp_path)
    silver_result = transform_bronze_run(bronze_store, bronze_manifest)
    silver_store = SilverFilesystemStore(tmp_path / "silver")
    published = silver_store.publish(silver_result, pipeline_version="test")
    return silver_store, published.manifest.dataset_id


def test_gold_publish_validates_and_reuses_complete_dataset(tmp_path: Path) -> None:
    """A complete Gold snapshot should round-trip and remain idempotent."""

    silver_store, silver_id = _create_silver(tmp_path)
    silver_manifest = silver_store.find_manifest(silver_id)
    assert silver_manifest is not None
    tokenizer = WhitespaceTokenizer()
    transformed = transform_silver_dataset(
        silver_store,
        silver_manifest,
        config=chunking_profiles()["tokens-300-v1"],
        tokenizer=tokenizer,
    )
    gold_store = GoldFilesystemStore(tmp_path / "gold")

    first = gold_store.publish(
        transformed,
        silver_store=silver_store,
        tokenizer=tokenizer,
        pipeline_version="test",
    )
    second = gold_store.publish(
        transformed,
        silver_store=silver_store,
        tokenizer=tokenizer,
        pipeline_version="test",
    )

    assert first.created is True
    assert second.created is False
    assert first.manifest == second.manifest
    assert len(gold_store.read_chunks(transformed.gold_dataset_id)) == 1
    report = validate_gold_dataset(
        gold_store,
        first.manifest,
        silver_store=silver_store,
        tokenizer=tokenizer,
    )
    assert report.is_valid


def test_gold_validation_reports_changed_parquet(tmp_path: Path) -> None:
    """A changed Gold artifact should fail its immutable receipt."""

    silver_store, silver_id = _create_silver(tmp_path)
    silver_manifest = silver_store.find_manifest(silver_id)
    assert silver_manifest is not None
    tokenizer = WhitespaceTokenizer()
    transformed = transform_silver_dataset(
        silver_store,
        silver_manifest,
        config=chunking_profiles()["tokens-300-v1"],
        tokenizer=tokenizer,
    )
    gold_store = GoldFilesystemStore(tmp_path / "gold")
    published = gold_store.publish(
        transformed,
        silver_store=silver_store,
        tokenizer=tokenizer,
        pipeline_version="test",
    )
    path = gold_store.dataset_directory(transformed.gold_dataset_id) / "chunks.parquet"
    path.write_bytes(path.read_bytes() + b"changed")

    report = validate_gold_dataset(
        gold_store,
        published.manifest,
        silver_store=silver_store,
        tokenizer=tokenizer,
    )

    assert {issue.code for issue in report.issues} >= {
        "byte_length_mismatch",
        "content_hash_mismatch",
    }


def test_gold_validation_recomputes_manifest_identity(tmp_path: Path) -> None:
    """A changed experiment scope must not retain the original dataset ID."""

    silver_store, silver_id = _create_silver(tmp_path)
    silver_manifest = silver_store.find_manifest(silver_id)
    assert silver_manifest is not None
    tokenizer = WhitespaceTokenizer()
    transformed = transform_silver_dataset(
        silver_store,
        silver_manifest,
        config=chunking_profiles()["tokens-300-v1"],
        tokenizer=tokenizer,
    )
    gold_store = GoldFilesystemStore(tmp_path / "gold")
    published = gold_store.publish(
        transformed,
        silver_store=silver_store,
        tokenizer=tokenizer,
        pipeline_version="test",
    )
    changed_scope = published.manifest.model_copy(
        update={
            "scope": GoldScope.SELECTED_WORKS,
            "selected_work_ids": ("work",),
        }
    )

    report = validate_gold_dataset(
        gold_store,
        changed_scope,
        silver_store=silver_store,
        tokenizer=tokenizer,
    )

    assert "dataset_identity_mismatch" in {issue.code for issue in report.issues}
