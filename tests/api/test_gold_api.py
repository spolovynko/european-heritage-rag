"""Tests for read-only Gold dataset and chunk inspection endpoints."""

import re
from pathlib import Path

from fastapi import status
from fastapi.testclient import TestClient

from european_heritage_rag.api.main import create_app
from european_heritage_rag.core.config import AppSettings, get_settings
from european_heritage_rag.domain.silver import (
    OcrQualityBand,
    SilverLineage,
    SilverPage,
    SilverQualityReport,
    SilverWork,
    WorkQualitySummary,
)
from european_heritage_rag.pipeline.bronze import BronzeResourceType
from european_heritage_rag.pipeline.chunking import chunking_profiles
from european_heritage_rag.pipeline.gold import transform_silver_dataset
from european_heritage_rag.pipeline.gold_store import GoldFilesystemStore
from european_heritage_rag.pipeline.silver import SilverTransformResult
from european_heritage_rag.pipeline.silver_store import SilverFilesystemStore
from european_heritage_rag.pipeline.tokenization import (
    DEFAULT_TOKENIZER_MAXIMUM_LENGTH,
    DEFAULT_TOKENIZER_MODEL,
    DEFAULT_TOKENIZER_REVISION,
    TokenTextSpan,
)


class WhitespaceTokenizer:
    """Small API-test tokenizer double with two special tokens."""

    model_id = DEFAULT_TOKENIZER_MODEL
    revision = DEFAULT_TOKENIZER_REVISION
    model_maximum_length = DEFAULT_TOKENIZER_MAXIMUM_LENGTH

    def content_offsets(self, text: str) -> tuple[tuple[int, int], ...]:
        return tuple(
            (match.start(), match.end()) for match in re.finditer(r"\S+", text)
        )

    def token_count(
        self,
        text: str,
        *,
        add_special_tokens: bool = True,
    ) -> int:
        return len(self.content_offsets(text)) + (2 if add_special_tokens else 0)

    def split_to_model_limit(
        self,
        text: str,
        maximum_token_count: int,
    ) -> tuple[TokenTextSpan, ...]:
        offsets = self.content_offsets(text)
        if not offsets:
            return ()
        return (TokenTextSpan(text=text, char_start=0, char_end=len(text)),)

    def trailing_content(self, text: str, token_count: int) -> TokenTextSpan:
        offsets = self.content_offsets(text)
        if not offsets or token_count <= 0:
            return TokenTextSpan("", len(text), len(text))
        start = offsets[-min(token_count, len(offsets))][0]
        return TokenTextSpan(text[start:], start, len(text))


def create_gold_fixture(tmp_path: Path) -> tuple[str, str]:
    """Publish one complete fixture dataset through Silver and Gold."""

    silver_id = "a" * 64
    catalogue_lineage = SilverLineage(
        resource_id="catalogue",
        resource_type=BronzeResourceType.CATALOGUE_WORK,
        relative_path="works/work/work.json",
        source_url="https://example.test/catalogue",
        content_sha256="b" * 64,
    )
    manifest_lineage = SilverLineage(
        resource_id="manifest",
        resource_type=BronzeResourceType.IIIF_MANIFEST,
        relative_path="works/work/manifest.json",
        source_url="https://example.test/manifest",
        content_sha256="c" * 64,
    )
    work = SilverWork(
        dataset_id=silver_id,
        work_id="work",
        title="Fixture work",
        language_ids=("eng",),
        language_labels=("English",),
        licence_id="pdm",
        licence_url="https://creativecommons.org/publicdomain/mark/1.0/",
        source_url="https://wellcomecollection.org/works/work",
        iiif_manifest_url="https://example.test/manifest",
        source_content_sha256="b" * 64,
        iiif_manifest_content_sha256="c" * 64,
        lineage=(catalogue_lineage, manifest_lineage),
    )
    page = SilverPage(
        dataset_id=silver_id,
        page_id="d" * 64,
        work_id="work",
        canvas_id="https://example.test/canvas/1",
        sequence_number=1,
        page_label="1",
        printed_page_number=1,
        raw_text="Cholera prevention requires clean water.",
        clean_text="Cholera prevention requires clean water.",
        ocr_quality=OcrQualityBand.USABLE,
        raw_line_count=1,
        raw_word_count=5,
        clean_word_count=5,
        cleaning_change_ratio=0,
        image_url="https://example.test/image/1.jpg",
        lineage=(manifest_lineage,),
    )
    quality = SilverQualityReport(
        dataset_id=silver_id,
        work_count=1,
        page_count=1,
        empty_page_count=0,
        review_page_count=0,
        usable_page_count=1,
        average_clean_word_count=5,
        language_counts={"eng": 1},
        works=(
            WorkQualitySummary(
                work_id="work",
                page_count=1,
                empty_page_count=0,
                review_page_count=0,
                average_clean_word_count=5,
            ),
        ),
    )
    silver_store = SilverFilesystemStore(tmp_path / "silver")
    silver = silver_store.publish(
        SilverTransformResult(
            dataset_id=silver_id,
            bronze_run_id="bronze-run",
            bronze_inventory_sha256="e" * 64,
            works=(work,),
            pages=(page,),
            quality_report=quality,
        ),
        pipeline_version="test",
    )
    tokenizer = WhitespaceTokenizer()
    transformed = transform_silver_dataset(
        silver_store,
        silver.manifest,
        config=chunking_profiles()["tokens-300-v1"],
        tokenizer=tokenizer,
    )
    gold = GoldFilesystemStore(tmp_path / "gold").publish(
        transformed,
        silver_store=silver_store,
        tokenizer=tokenizer,
        pipeline_version="test",
    )
    return gold.manifest.gold_dataset_id, transformed.chunks[0].chunk_id


def test_gold_endpoints_list_filter_and_show_chunk(tmp_path: Path) -> None:
    """API should expose bounded summaries and full selected chunk evidence."""

    dataset_id, chunk_id = create_gold_fixture(tmp_path)
    settings = AppSettings(
        _env_file=None,
        app_env="test",
        silver_data_directory=tmp_path / "silver",
        gold_data_directory=tmp_path / "gold",
    )
    application = create_app(tmp_path / "missing-frontend")
    application.dependency_overrides[get_settings] = lambda: settings

    with TestClient(application) as client:
        datasets = client.get("/gold/datasets")
        works = client.get(f"/gold/datasets/{dataset_id}/works")
        chunks = client.get(
            f"/gold/datasets/{dataset_id}/chunks",
            params={"work_id": "work"},
        )
        detail = client.get(f"/gold/datasets/{dataset_id}/chunks/{chunk_id}")
        statistics = client.get(f"/gold/datasets/{dataset_id}/statistics")

    assert datasets.status_code == status.HTTP_200_OK
    assert datasets.json()[0]["gold_dataset_id"] == dataset_id
    assert works.json()[0]["work_id"] == "work"
    assert chunks.json()["total"] == 1
    assert "text" not in chunks.json()["items"][0]
    assert detail.json()["page_spans"][0]["sequence_number"] == 1
    assert statistics.json()["chunk_count"] == 1


def test_gold_endpoints_return_not_found(tmp_path: Path) -> None:
    """Unknown Gold identities should return normal not-found responses."""

    settings = AppSettings(
        _env_file=None,
        app_env="test",
        gold_data_directory=tmp_path / "gold",
    )
    application = create_app(tmp_path / "missing-frontend")
    application.dependency_overrides[get_settings] = lambda: settings

    with TestClient(application) as client:
        missing = client.get("/gold/datasets/missing")

    assert missing.status_code == status.HTTP_404_NOT_FOUND
