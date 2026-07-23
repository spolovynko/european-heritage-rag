"""Small deterministic OCR reconstruction and cleaning functions."""

import html
import re
import unicodedata
from dataclasses import dataclass
from html.parser import HTMLParser
from statistics import median

_HORIZONTAL_WHITESPACE = re.compile(r"[^\S\n]+")
_HTML_TAG = re.compile(r"</?[A-Za-z][^>]*>")
_SELECTOR = re.compile(
    r"(?:#|&)xywh=(?P<x>\d+),(?P<y>\d+),(?P<width>\d+),(?P<height>\d+)"
)
_WORD = re.compile(r"\b[\w’'-]+\b", flags=re.UNICODE)


@dataclass(frozen=True, slots=True)
class OcrLine:
    """One source OCR line with optional IIIF pixel coordinates."""

    text: str
    x: int | None = None
    y: int | None = None
    width: int | None = None
    height: int | None = None


@dataclass(frozen=True, slots=True)
class CleaningResult:
    """Cleaned page text plus transparent transformation counts."""

    clean_text: str
    html_removed_count: int
    dehyphenation_count: int
    removed_header_count: int
    removed_footer_count: int


class _TextExtractor(HTMLParser):
    """Collect text content while discarding HTML tags."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def parse_ocr_line(text: str, selector: str) -> OcrLine:
    """Create an OCR line and parse a valid IIIF xywh selector when present."""

    match = _SELECTOR.search(selector)
    if match is None:
        return OcrLine(text=text)
    values = {name: int(value) for name, value in match.groupdict().items()}
    return OcrLine(text=text, **values)


def raw_text_from(lines: tuple[OcrLine, ...]) -> str:
    """Preserve source OCR line order without cleaning."""

    return "\n".join(line.text for line in lines)


def normalize_unicode(text: str) -> str:
    """Use conservative NFC normalization."""

    return unicodedata.normalize("NFC", text)


def strip_html(text: str) -> tuple[str, bool]:
    """Remove confirmed HTML tags while preserving visible character data."""

    if _HTML_TAG.search(text) is None:
        return html.unescape(text), False
    parser = _TextExtractor()
    parser.feed(text)
    parser.close()
    return "".join(parser.parts), True


def normalize_horizontal_whitespace(text: str) -> str:
    """Collapse horizontal whitespace without erasing paragraph newlines."""

    return _HORIZONTAL_WHITESPACE.sub(" ", text).strip()


def join_ocr_lines(lines: tuple[str, ...]) -> tuple[str, int]:
    """Join wrapped lines and conservatively dehyphenate word continuations."""

    paragraphs: list[str] = []
    current = ""
    dehyphenation_count = 0

    for line in lines:
        normalized = normalize_horizontal_whitespace(line)
        if not normalized:
            if current:
                paragraphs.append(current.strip())
                current = ""
            continue

        if not current:
            current = normalized
            continue

        previous_character = current[-2] if len(current) >= 2 else ""
        first_character = normalized[0]
        may_dehyphenate = (
            current.endswith(("-", "\u00ad"))
            and previous_character.isalpha()
            and first_character.isalpha()
            and first_character.islower()
        )
        if may_dehyphenate:
            current = f"{current[:-1]}{normalized}"
            dehyphenation_count += 1
        else:
            current = f"{current} {normalized}"

    if current:
        paragraphs.append(current.strip())

    return "\n\n".join(paragraphs), dehyphenation_count


def clean_ocr_lines(
    lines: tuple[OcrLine, ...],
    *,
    header_lines: frozenset[str] = frozenset(),
    footer_lines: frozenset[str] = frozenset(),
) -> CleaningResult:
    """Apply the explicit conservative page-cleaning pipeline."""

    cleaned_lines: list[str] = []
    html_removed_count = 0
    removed_header_count = 0
    removed_footer_count = 0

    for line in lines:
        if line.text in header_lines:
            removed_header_count += 1
            continue
        if line.text in footer_lines:
            removed_footer_count += 1
            continue

        normalized = normalize_unicode(line.text)
        without_html, removed = strip_html(normalized)
        html_removed_count += int(removed)
        cleaned_lines.append(without_html)

    clean_text, dehyphenation_count = join_ocr_lines(tuple(cleaned_lines))
    return CleaningResult(
        clean_text=clean_text,
        html_removed_count=html_removed_count,
        dehyphenation_count=dehyphenation_count,
        removed_header_count=removed_header_count,
        removed_footer_count=removed_footer_count,
    )


def word_count(text: str) -> int:
    """Count Unicode word-like tokens for transparent quality heuristics."""

    return len(_WORD.findall(text))


def symbol_ratio(text: str) -> float:
    """Return the share of non-space characters that are not letters or digits."""

    non_space = [character for character in text if not character.isspace()]
    if not non_space:
        return 0.0
    symbols = sum(not character.isalnum() for character in non_space)
    return symbols / len(non_space)


def cleaning_change_ratio(raw_text: str, clean_text: str) -> float:
    """Return a simple visible size-change ratio, not semantic edit distance."""

    if not raw_text:
        return 0.0 if not clean_text else 1.0
    return abs(len(raw_text) - len(clean_text)) / len(raw_text)


def median_line_height(lines: tuple[OcrLine, ...]) -> float | None:
    """Return median available OCR line height for later layout heuristics."""

    heights = [line.height for line in lines if line.height is not None]
    return float(median(heights)) if heights else None
