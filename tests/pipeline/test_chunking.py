"""Tests for page-aware token chunking and provenance."""

from hashlib import sha256

from gold_test_support import WhitespaceTokenizer
from pydantic import AnyHttpUrl

from european_heritage_rag.domain.silver import (
    OcrQualityBand,
    PageQualityFlag,
    SilverContributor,
    SilverLineage,
    SilverPage,
    SilverWork,
)
from european_heritage_rag.pipeline.bronze import BronzeResourceType
from european_heritage_rag.pipeline.chunking import chunk_work, chunking_profiles

_DATASET_ID = sha256(b"silver").hexdigest()


def _lineage(resource_id: str, resource_type: BronzeResourceType) -> SilverLineage:
    return SilverLineage(
        resource_id=resource_id,
        resource_type=resource_type,
        relative_path=f"works/work/{resource_id}.json",
        source_url=AnyHttpUrl(f"https://example.test/{resource_id}"),
        content_sha256=sha256(resource_id.encode()).hexdigest(),
    )


def _work() -> SilverWork:
    return SilverWork(
        dataset_id=_DATASET_ID,
        work_id="work",
        title="A test work",
        contributors=(SilverContributor(label="Ada Author", primary=True),),
        language_ids=("eng",),
        language_labels=("English",),
        licence_id="pdm",
        licence_url=AnyHttpUrl("https://creativecommons.org/publicdomain/mark/1.0/"),
        source_url=AnyHttpUrl("https://example.test/work"),
        iiif_manifest_url=AnyHttpUrl("https://example.test/manifest"),
        source_content_sha256=sha256(b"work").hexdigest(),
        iiif_manifest_content_sha256=sha256(b"manifest").hexdigest(),
        lineage=(
            _lineage("catalogue", BronzeResourceType.CATALOGUE_WORK),
            _lineage("manifest", BronzeResourceType.IIIF_MANIFEST),
        ),
    )


def _page(sequence: int, text: str) -> SilverPage:
    missing = not text.strip()
    return SilverPage(
        dataset_id=_DATASET_ID,
        page_id=sha256(f"page-{sequence}".encode()).hexdigest(),
        work_id="work",
        canvas_id=AnyHttpUrl(f"https://example.test/canvas/{sequence}"),
        sequence_number=sequence,
        page_label=str(sequence),
        printed_page_number=sequence,
        raw_text=text,
        clean_text=text,
        ocr_quality=OcrQualityBand.MISSING if missing else OcrQualityBand.USABLE,
        quality_flags=(PageQualityFlag.EMPTY_OCR,) if missing else (),
        raw_line_count=0 if missing else 1,
        raw_word_count=len(text.split()),
        clean_word_count=len(text.split()),
        cleaning_change_ratio=0,
        image_url=AnyHttpUrl(f"https://example.test/image/{sequence}.jpg"),
        lineage=(_lineage(f"page-{sequence}", BronzeResourceType.IIIF_MANIFEST),),
    )


def _words(prefix: str, count: int) -> str:
    return " ".join(f"{prefix}{index}" for index in range(count))


def test_chunking_is_stable_bounded_and_page_aware() -> None:
    """Repeated builds should preserve IDs, limits, order, and page citations."""

    config = chunking_profiles()["tokens-300-v1"]
    tokenizer = WhitespaceTokenizer()
    pages = (_page(1, _words("a", 220)), _page(2, _words("b", 220)))

    first = chunk_work(
        _work(),
        pages,
        gold_dataset_id=sha256(b"gold").hexdigest(),
        config=config,
        tokenizer=tokenizer,
    )
    second = chunk_work(
        _work(),
        pages,
        gold_dataset_id=sha256(b"gold").hexdigest(),
        config=config,
        tokenizer=tokenizer,
    )

    assert [(chunk.chunk_id, chunk.text) for chunk in first] == [
        (chunk.chunk_id, chunk.text) for chunk in second
    ]
    assert all(chunk.token_count <= config.maximum_token_count for chunk in first)
    assert all(
        tuple(span.sequence_number for span in chunk.page_spans)
        == tuple(sorted(span.sequence_number for span in chunk.page_spans))
        for chunk in first
    )
    assert {span.page_id for chunk in first for span in chunk.page_spans} == {
        page.page_id for page in pages
    }
    assert first[1].overlap_previous_token_count > 0
    assert first[0].next_chunk_id == first[1].chunk_id
    assert first[1].previous_chunk_id == first[0].chunk_id


def test_empty_page_is_a_hard_boundary() -> None:
    """A missing-OCR page must prevent a citation range from bridging the gap."""

    chunks = chunk_work(
        _work(),
        (
            _page(1, _words("a", 60)),
            _page(2, ""),
            _page(3, _words("c", 60)),
        ),
        gold_dataset_id=sha256(b"gold").hexdigest(),
        config=chunking_profiles()["tokens-300-v1"],
        tokenizer=WhitespaceTokenizer(),
    )

    assert len(chunks) == 2
    assert [
        (chunk.page_sequence_start, chunk.page_sequence_end) for chunk in chunks
    ] == [
        (1, 1),
        (3, 3),
    ]
    assert all(chunk.overlap_previous_token_count == 0 for chunk in chunks)


def test_oversized_page_uses_hard_token_fallback() -> None:
    """A single unstructured page should split without exceeding the model limit."""

    config = chunking_profiles()["tokens-300-v1"]
    chunks = chunk_work(
        _work(),
        (_page(1, _words("long", 900)),),
        gold_dataset_id=sha256(b"gold").hexdigest(),
        config=config,
        tokenizer=WhitespaceTokenizer(),
    )

    assert len(chunks) >= 3
    assert max(chunk.token_count for chunk in chunks) <= config.maximum_token_count
    assert {span.page_id for chunk in chunks for span in chunk.page_spans} == {
        sha256(b"page-1").hexdigest()
    }
