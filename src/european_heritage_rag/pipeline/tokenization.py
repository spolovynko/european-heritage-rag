"""Pinned embedding-tokenizer boundary used by deterministic chunking."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol, cast

DEFAULT_TOKENIZER_MODEL = "BAAI/bge-m3"
DEFAULT_TOKENIZER_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
DEFAULT_TOKENIZER_MAXIMUM_LENGTH = 8192


class TokenBoundary(Protocol):
    """Minimal token behavior required by the explicit chunker."""

    model_id: str
    revision: str
    model_maximum_length: int

    def token_count(
        self,
        text: str,
        *,
        add_special_tokens: bool = True,
    ) -> int:
        """Return the exact tokenizer count for text."""

    def content_offsets(self, text: str) -> tuple[tuple[int, int], ...]:
        """Return half-open character offsets for content tokens."""

    def split_to_model_limit(
        self,
        text: str,
        maximum_token_count: int,
    ) -> tuple["TokenTextSpan", ...]:
        """Split text into non-empty spans within a model-token maximum."""

    def trailing_content(
        self,
        text: str,
        token_count: int,
    ) -> "TokenTextSpan":
        """Return up to the requested trailing content tokens."""


@dataclass(frozen=True, slots=True)
class TokenTextSpan:
    """A tokenizer-aligned text slice and offsets in its parent string."""

    text: str
    char_start: int
    char_end: int


class PinnedTokenizer:
    """Fast tokenizer loaded from an immutable Hugging Face model revision."""

    def __init__(
        self,
        *,
        model_id: str = DEFAULT_TOKENIZER_MODEL,
        revision: str = DEFAULT_TOKENIZER_REVISION,
        expected_maximum_length: int = DEFAULT_TOKENIZER_MAXIMUM_LENGTH,
        local_files_only: bool = False,
    ) -> None:
        from transformers import AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(
            model_id,
            revision=revision,
            use_fast=True,
            local_files_only=local_files_only,
        )
        if not tokenizer.is_fast:
            raise ValueError("Gold chunking requires a fast tokenizer with offsets")
        if tokenizer.model_max_length != expected_maximum_length:
            raise ValueError(
                "tokenizer maximum length changed: "
                f"{tokenizer.model_max_length} != {expected_maximum_length}"
            )
        self.model_id = model_id
        self.revision = revision
        self.model_maximum_length = expected_maximum_length
        self._tokenizer: Any = tokenizer

    def token_count(
        self,
        text: str,
        *,
        add_special_tokens: bool = True,
    ) -> int:
        """Count input IDs without padding or truncation."""

        encoded = self._tokenizer(
            text,
            add_special_tokens=add_special_tokens,
            padding=False,
            truncation=False,
        )
        input_ids = cast(Sequence[int], encoded["input_ids"])
        return len(input_ids)

    def content_offsets(self, text: str) -> tuple[tuple[int, int], ...]:
        """Return validated offsets from the fast tokenizer."""

        if not text:
            return ()
        encoded = self._tokenizer(
            text,
            add_special_tokens=False,
            padding=False,
            truncation=False,
            return_offsets_mapping=True,
        )
        raw_offsets = cast(Sequence[Sequence[int]], encoded["offset_mapping"])
        offsets = tuple((int(item[0]), int(item[1])) for item in raw_offsets)
        return tuple(offset for offset in offsets if offset[1] > offset[0])

    def split_to_model_limit(
        self,
        text: str,
        maximum_token_count: int,
    ) -> tuple[TokenTextSpan, ...]:
        """Split at tokenizer offsets while preserving every visible character."""

        if not text.strip():
            return ()
        special_tokens = self.token_count("", add_special_tokens=True)
        capacity = maximum_token_count - special_tokens
        if capacity < 1:
            raise ValueError("maximum_token_count leaves no content-token capacity")
        offsets = self.content_offsets(text)
        if not offsets:
            return ()
        spans: list[TokenTextSpan] = []
        for token_start in range(0, len(offsets), capacity):
            token_end = min(token_start + capacity, len(offsets))
            char_start = 0 if token_start == 0 else offsets[token_start][0]
            char_end = (
                len(text) if token_end == len(offsets) else offsets[token_end - 1][1]
            )
            span = _trim_span(text, char_start, char_end)
            if span is not None:
                spans.append(span)
        return tuple(spans)

    def trailing_content(
        self,
        text: str,
        token_count: int,
    ) -> TokenTextSpan:
        """Return a tokenizer-aligned suffix without adding model tokens."""

        if token_count <= 0 or not text:
            return TokenTextSpan(text="", char_start=len(text), char_end=len(text))
        offsets = self.content_offsets(text)
        if not offsets:
            return TokenTextSpan(text="", char_start=len(text), char_end=len(text))
        selected = min(token_count, len(offsets))
        char_start = offsets[-selected][0]
        trimmed = _trim_span(text, char_start, len(text))
        if trimmed is None:
            return TokenTextSpan(text="", char_start=len(text), char_end=len(text))
        return trimmed


def _trim_span(text: str, char_start: int, char_end: int) -> TokenTextSpan | None:
    """Trim boundary whitespace and retain offsets into the parent string."""

    while char_start < char_end and text[char_start].isspace():
        char_start += 1
    while char_end > char_start and text[char_end - 1].isspace():
        char_end -= 1
    if char_end <= char_start:
        return None
    return TokenTextSpan(
        text=text[char_start:char_end],
        char_start=char_start,
        char_end=char_end,
    )
