"""Small deterministic helpers shared by Gold pipeline tests."""

import re

from european_heritage_rag.pipeline.tokenization import (
    DEFAULT_TOKENIZER_MAXIMUM_LENGTH,
    DEFAULT_TOKENIZER_MODEL,
    DEFAULT_TOKENIZER_REVISION,
    TokenTextSpan,
)


class WhitespaceTokenizer:
    """Predictable tokenizer double with two model special tokens."""

    model_id = DEFAULT_TOKENIZER_MODEL
    revision = DEFAULT_TOKENIZER_REVISION
    model_maximum_length = DEFAULT_TOKENIZER_MAXIMUM_LENGTH

    def token_count(
        self,
        text: str,
        *,
        add_special_tokens: bool = True,
    ) -> int:
        count = len(self.content_offsets(text))
        return count + 2 if add_special_tokens else count

    def content_offsets(self, text: str) -> tuple[tuple[int, int], ...]:
        return tuple(
            (match.start(), match.end()) for match in re.finditer(r"\S+", text)
        )

    def split_to_model_limit(
        self,
        text: str,
        maximum_token_count: int,
    ) -> tuple[TokenTextSpan, ...]:
        capacity = maximum_token_count - 2
        offsets = self.content_offsets(text)
        spans: list[TokenTextSpan] = []
        for start in range(0, len(offsets), capacity):
            end = min(start + capacity, len(offsets))
            char_start = 0 if start == 0 else offsets[start][0]
            char_end = len(text) if end == len(offsets) else offsets[end - 1][1]
            while char_start < char_end and text[char_start].isspace():
                char_start += 1
            while char_end > char_start and text[char_end - 1].isspace():
                char_end -= 1
            if char_end > char_start:
                spans.append(
                    TokenTextSpan(
                        text=text[char_start:char_end],
                        char_start=char_start,
                        char_end=char_end,
                    )
                )
        return tuple(spans)

    def trailing_content(self, text: str, token_count: int) -> TokenTextSpan:
        offsets = self.content_offsets(text)
        if not offsets or token_count <= 0:
            return TokenTextSpan("", len(text), len(text))
        start = offsets[-min(token_count, len(offsets))][0]
        return TokenTextSpan(text[start:], start, len(text))
