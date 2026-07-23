"""Tests for conservative repeated work-boundary detection."""

from european_heritage_rag.pipeline.header_footer import (
    boundary_signature,
    detect_repeated_boundaries,
)
from european_heritage_rag.pipeline.ocr_cleaning import OcrLine


def test_repeated_headers_and_numbered_footers_are_detected() -> None:
    """Meaningful repeating boundaries should match across pages."""

    pages = tuple(
        (
            OcrLine("CHOLERA"),
            OcrLine(f"Page content {index}"),
            OcrLine(str(index)),
        )
        for index in range(1, 5)
    )

    matches = detect_repeated_boundaries(pages)

    assert all(headers == frozenset({"CHOLERA"}) for headers in matches.headers_by_page)
    assert all(footers == frozenset() for footers in matches.footers_by_page)


def test_punctuation_noise_is_not_a_candidate() -> None:
    """Repeated OCR punctuation should not be removed as a footer."""

    pages = tuple((OcrLine("Content"), OcrLine(".")) for _ in range(5))

    matches = detect_repeated_boundaries(pages)

    assert all(footers == frozenset() for footers in matches.footers_by_page)
    assert boundary_signature("■") is None


def test_too_few_repetitions_do_not_qualify() -> None:
    """Two matching lines are insufficient for automatic removal."""

    pages = (
        (OcrLine("HEADER"), OcrLine("One")),
        (OcrLine("HEADER"), OcrLine("Two")),
    )

    matches = detect_repeated_boundaries(pages)

    assert all(headers == frozenset() for headers in matches.headers_by_page)
