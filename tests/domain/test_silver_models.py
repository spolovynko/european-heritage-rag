"""Tests for canonical Silver domain model contracts."""

import pytest
from pydantic import ValidationError

from european_heritage_rag.domain.silver import (
    OcrQualityBand,
    PageQualityFlag,
    SilverLineage,
    SilverPage,
)
from european_heritage_rag.pipeline.bronze import BronzeResourceType

_HASH = "a" * 64


def lineage() -> SilverLineage:
    """Return one valid source lineage reference."""

    return SilverLineage(
        resource_id="iiif_manifest:work-1",
        resource_type=BronzeResourceType.IIIF_MANIFEST,
        relative_path="works/work-1/manifest.json",
        source_url="https://example.test/manifest",
        content_sha256=_HASH,
    )


def test_missing_ocr_page_requires_empty_flag() -> None:
    """Missing OCR should be explicit and internally consistent."""

    page = SilverPage(
        dataset_id=_HASH,
        page_id="b" * 64,
        work_id="work-1",
        canvas_id="https://example.test/canvas/1",
        sequence_number=1,
        page_label="-",
        raw_text="",
        clean_text="",
        ocr_quality=OcrQualityBand.MISSING,
        quality_flags=(PageQualityFlag.EMPTY_OCR,),
        raw_line_count=0,
        raw_word_count=0,
        clean_word_count=0,
        cleaning_change_ratio=0,
        lineage=(lineage(),),
    )

    assert page.printed_page_number is None
    assert page.ocr_quality is OcrQualityBand.MISSING


def test_missing_quality_rejects_nonempty_clean_text() -> None:
    """A page cannot claim missing OCR while containing usable clean text."""

    with pytest.raises(ValidationError):
        SilverPage(
            dataset_id=_HASH,
            page_id="b" * 64,
            work_id="work-1",
            canvas_id="https://example.test/canvas/1",
            sequence_number=1,
            page_label="1",
            printed_page_number=1,
            raw_text="Text",
            clean_text="Text",
            ocr_quality=OcrQualityBand.MISSING,
            quality_flags=(PageQualityFlag.EMPTY_OCR,),
            raw_line_count=1,
            raw_word_count=1,
            clean_word_count=1,
            cleaning_change_ratio=0,
            lineage=(lineage(),),
        )


def test_duplicate_quality_flags_are_rejected() -> None:
    """Flags should be set-like and deterministic."""

    with pytest.raises(ValidationError):
        SilverPage(
            dataset_id=_HASH,
            page_id="b" * 64,
            work_id="work-1",
            canvas_id="https://example.test/canvas/1",
            sequence_number=1,
            page_label="1",
            raw_text="Short",
            clean_text="Short",
            ocr_quality=OcrQualityBand.NEEDS_REVIEW,
            quality_flags=(
                PageQualityFlag.VERY_SHORT_TEXT,
                PageQualityFlag.VERY_SHORT_TEXT,
            ),
            raw_line_count=1,
            raw_word_count=1,
            clean_word_count=1,
            cleaning_change_ratio=0,
            lineage=(lineage(),),
        )
