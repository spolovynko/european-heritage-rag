"""Tests for conservative pure OCR cleaning."""

from european_heritage_rag.pipeline.ocr_cleaning import (
    OcrLine,
    clean_ocr_lines,
    join_ocr_lines,
    normalize_unicode,
    parse_ocr_line,
    raw_text_from,
)


def test_unicode_normalization_uses_nfc() -> None:
    """Equivalent composed and decomposed text should normalize identically."""

    assert normalize_unicode("cafe\u0301") == "café"


def test_html_whitespace_and_raw_text_remain_separate() -> None:
    """Cleaning may remove markup without changing reconstructed raw text."""

    lines = (
        OcrLine("<b>CHOLERA</b>"),
        OcrLine("  spread\u00a0rapidly  "),
    )

    result = clean_ocr_lines(lines)

    assert raw_text_from(lines) == "<b>CHOLERA</b>\n  spread\u00a0rapidly  "
    assert result.clean_text == "CHOLERA spread rapidly"
    assert result.html_removed_count == 1


def test_safe_dehyphenation_and_paragraph_preservation() -> None:
    """Lowercase word continuation joins while blank lines preserve paragraphs."""

    clean_text, count = join_ocr_lines(
        ("The preven-", "tion measure", "", "Second paragraph.")
    )

    assert clean_text == "The prevention measure\n\nSecond paragraph."
    assert count == 1


def test_ambiguous_hyphen_is_preserved() -> None:
    """An uppercase next line is not assumed to continue a split word."""

    clean_text, count = join_ocr_lines(("well-", "Being matters"))

    assert clean_text == "well- Being matters"
    assert count == 0


def test_parse_ocr_line_extracts_xywh() -> None:
    """IIIF selectors should expose optional layout evidence."""

    line = parse_ocr_line(
        "Text",
        "https://example.test/canvas#xywh=10,20,300,40",
    )

    assert (line.x, line.y, line.width, line.height) == (10, 20, 300, 40)


def test_confirmed_header_and_footer_are_removed_transparently() -> None:
    """Only caller-confirmed boundary lines should leave clean text."""

    lines = (
        OcrLine("RUNNING HEADER"),
        OcrLine("Main text"),
        OcrLine("12"),
    )

    result = clean_ocr_lines(
        lines,
        header_lines=frozenset({"RUNNING HEADER"}),
        footer_lines=frozenset({"12"}),
    )

    assert result.clean_text == "Main text"
    assert result.removed_header_count == 1
    assert result.removed_footer_count == 1
