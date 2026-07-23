"""Conservative repeated header and footer detection across one work."""

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass

from european_heritage_rag.pipeline.ocr_cleaning import OcrLine

_DIGITS = re.compile(r"\d+")
_SPACES = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class BoundaryMatches:
    """Original page lines confirmed as repeated work boundaries."""

    headers_by_page: tuple[frozenset[str], ...]
    footers_by_page: tuple[frozenset[str], ...]


def boundary_signature(text: str) -> str | None:
    """Normalize a candidate for comparison and reject punctuation noise."""

    normalized = unicodedata.normalize("NFC", text).casefold().strip()
    normalized = _DIGITS.sub("#", normalized)
    normalized = _SPACES.sub(" ", normalized)
    if sum(character.isalnum() for character in normalized) < 4:
        return None
    return normalized


def detect_repeated_boundaries(
    pages: tuple[tuple[OcrLine, ...], ...],
) -> BoundaryMatches:
    """Detect high-confidence repeated lines among page tops and bottoms."""

    text_pages = [lines for lines in pages if any(line.text.strip() for line in lines)]
    minimum_occurrences = max(3, math.ceil(len(text_pages) * 0.15))

    top_candidates: list[list[tuple[str, str]]] = []
    bottom_candidates: list[list[tuple[str, str]]] = []
    top_counts: Counter[str] = Counter()
    bottom_counts: Counter[str] = Counter()

    for lines in pages:
        non_empty = [line.text for line in lines if line.text.strip()]
        top = _candidate_pairs(non_empty[:1])
        bottom = _candidate_pairs(non_empty[-1:])
        top_candidates.append(top)
        bottom_candidates.append(bottom)
        top_counts.update({signature for _, signature in top})
        bottom_counts.update({signature for _, signature in bottom})

    repeated_headers = {
        signature
        for signature, count in top_counts.items()
        if count >= minimum_occurrences
    }
    repeated_footers = {
        signature
        for signature, count in bottom_counts.items()
        if count >= minimum_occurrences
    }

    return BoundaryMatches(
        headers_by_page=tuple(
            frozenset(
                original
                for original, signature in candidates
                if signature in repeated_headers
            )
            for candidates in top_candidates
        ),
        footers_by_page=tuple(
            frozenset(
                original
                for original, signature in candidates
                if signature in repeated_footers
            )
            for candidates in bottom_candidates
        ),
    )


def _candidate_pairs(lines: list[str]) -> list[tuple[str, str]]:
    """Return original/signature pairs for meaningful boundary lines."""

    candidates: list[tuple[str, str]] = []
    for line in lines:
        signature = boundary_signature(line)
        if signature is not None:
            candidates.append((line, signature))
    return candidates
