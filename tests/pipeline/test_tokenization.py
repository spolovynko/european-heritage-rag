"""Tests for the immutable fast-tokenizer adapter."""

import re
from typing import Any

import pytest
import transformers

from european_heritage_rag.pipeline.tokenization import PinnedTokenizer


class _FakeFastTokenizer:
    """Small Hugging Face-shaped tokenizer for adapter-level unit tests."""

    is_fast = True
    model_max_length = 8192

    def __call__(
        self,
        text: str,
        *,
        add_special_tokens: bool,
        return_offsets_mapping: bool = False,
        **_: Any,
    ) -> dict[str, Any]:
        offsets = tuple(match.span() for match in re.finditer(r"\S+", text))
        ids = list(range(1, len(offsets) + 1))
        if add_special_tokens:
            ids = [0, *ids, 2]
        result: dict[str, Any] = {"input_ids": ids}
        if return_offsets_mapping:
            result["offset_mapping"] = offsets
        return result


def test_pinned_tokenizer_uses_revision_and_preserves_token_boundaries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The adapter should load immutably and split only at tokenizer offsets."""

    calls: list[tuple[str, dict[str, Any]]] = []

    def fake_from_pretrained(model_id: str, **kwargs: Any) -> _FakeFastTokenizer:
        calls.append((model_id, kwargs))
        return _FakeFastTokenizer()

    monkeypatch.setattr(
        transformers.AutoTokenizer, "from_pretrained", fake_from_pretrained
    )
    tokenizer = PinnedTokenizer(
        model_id="example/model",
        revision="immutable-commit",
        local_files_only=True,
    )
    text = "one two three four five six seven"

    assert calls == [
        (
            "example/model",
            {
                "revision": "immutable-commit",
                "use_fast": True,
                "local_files_only": True,
            },
        )
    ]
    assert tokenizer.token_count(text) == 9
    assert [span.text for span in tokenizer.split_to_model_limit(text, 5)] == [
        "one two three",
        "four five six",
        "seven",
    ]
    assert tokenizer.trailing_content(text, 2).text == "six seven"


def test_pinned_tokenizer_rejects_changed_model_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A changed upstream model limit must fail instead of silently drifting."""

    tokenizer = _FakeFastTokenizer()
    tokenizer.model_max_length = 4096
    monkeypatch.setattr(
        transformers.AutoTokenizer,
        "from_pretrained",
        lambda *_args, **_kwargs: tokenizer,
    )

    with pytest.raises(ValueError, match="tokenizer maximum length changed"):
        PinnedTokenizer()
