"""Explicit page-aware, token-bounded Gold chunk construction."""

import json
import re
from dataclasses import dataclass, replace
from hashlib import sha256
from typing import Final

from european_heritage_rag.domain.gold import (
    ChunkingConfig,
    ChunkPageSpan,
    GoldChunk,
)
from european_heritage_rag.domain.silver import SilverPage, SilverWork
from european_heritage_rag.pipeline.tokenization import (
    DEFAULT_TOKENIZER_MAXIMUM_LENGTH,
    DEFAULT_TOKENIZER_MODEL,
    DEFAULT_TOKENIZER_REVISION,
    TokenBoundary,
)

GOLD_SCHEMA_VERSION: Final = 1
CHUNKER_VERSION = "page-aware-token-v1"
_STRUCTURAL_GAP = re.compile(r"\n{2,}|(?<=[.!?])\s+")


class ChunkingError(RuntimeError):
    """Raised when Silver rows cannot be chunked without losing provenance."""


@dataclass(frozen=True, slots=True)
class _Fragment:
    """One source-page text slice used by the greedy accumulator."""

    page: SilverPage
    text: str
    source_char_start: int
    source_char_end: int


@dataclass(frozen=True, slots=True)
class _Draft:
    """A chunk before stable identity and adjacency links are attached."""

    fragments: tuple[_Fragment, ...]
    overlap_fragment_count: int = 0


@dataclass(frozen=True, slots=True)
class _RenderedDraft:
    """Rendered draft and derived page/overlap evidence."""

    text: str
    page_spans: tuple[ChunkPageSpan, ...]
    token_count: int
    overlap_token_count: int
    overlap_prefix_char_end: int


@dataclass(slots=True)
class _PageRange:
    """Mutable aggregation state for one page inside rendered chunk text."""

    page: SilverPage
    chunk_char_start: int
    chunk_char_end: int
    source_char_start: int
    source_char_end: int


def chunking_profiles() -> dict[str, ChunkingConfig]:
    """Return the three named, versioned Phase 7 experiments."""

    return {
        "tokens-300-v1": _profile("tokens-300-v1", 300, 360, 30),
        "tokens-500-v1": _profile("tokens-500-v1", 500, 600, 50),
        "tokens-800-v1": _profile("tokens-800-v1", 800, 960, 80),
    }


def _profile(
    profile_id: str,
    target: int,
    maximum: int,
    overlap: int,
) -> ChunkingConfig:
    """Construct one profile with the shared pinned tokenizer policy."""

    return ChunkingConfig(
        profile_id=profile_id,
        target_token_count=target,
        maximum_token_count=maximum,
        overlap_token_count=overlap,
        minimum_token_count=50,
        tokenizer_model=DEFAULT_TOKENIZER_MODEL,
        tokenizer_revision=DEFAULT_TOKENIZER_REVISION,
        tokenizer_maximum_length=DEFAULT_TOKENIZER_MAXIMUM_LENGTH,
        chunker_version=CHUNKER_VERSION,
        eligible_language_id="eng",
        require_single_language=True,
    )


def chunk_work(
    work: SilverWork,
    pages: tuple[SilverPage, ...],
    *,
    gold_dataset_id: str,
    config: ChunkingConfig,
    tokenizer: TokenBoundary,
) -> tuple[GoldChunk, ...]:
    """Create ordered chunks for one unambiguously eligible work."""

    if pages and work.dataset_id != pages[0].dataset_id:
        raise ChunkingError(f"work {work.work_id} and pages use different datasets")
    if config.require_single_language and work.language_ids != (
        config.eligible_language_id,
    ):
        raise ChunkingError(
            f"work {work.work_id} is not unambiguously {config.eligible_language_id}"
        )
    ordered_pages = tuple(sorted(pages, key=lambda item: item.sequence_number))
    if len({page.page_id for page in ordered_pages}) != len(ordered_pages):
        raise ChunkingError(f"work {work.work_id} contains duplicate page IDs")
    if any(page.work_id != work.work_id for page in ordered_pages):
        raise ChunkingError(f"work {work.work_id} received a foreign page")
    sequences = tuple(page.sequence_number for page in ordered_pages)
    if sequences != tuple(sorted(sequences)):
        raise ChunkingError(f"work {work.work_id} page order is invalid")

    drafts: list[_Draft] = []
    current_run: list[_Fragment] = []
    for page in ordered_pages:
        if not page.clean_text.strip():
            drafts.extend(_chunk_fragment_run(tuple(current_run), config, tokenizer))
            current_run = []
            continue
        current_run.extend(_page_fragments(page, config, tokenizer))
    drafts.extend(_chunk_fragment_run(tuple(current_run), config, tokenizer))

    rendered = tuple(_render_draft(draft, tokenizer) for draft in drafts)
    prepared: list[tuple[str, _RenderedDraft]] = []
    for chunk_index, item in enumerate(rendered):
        content_hash = sha256(item.text.encode()).hexdigest()
        identity_payload = {
            "work_id": work.work_id,
            "page_ids": [span.page_id for span in item.page_spans],
            "page_sequence_start": item.page_spans[0].sequence_number,
            "page_sequence_end": item.page_spans[-1].sequence_number,
            "profile_id": config.profile_id,
            "chunker_version": config.chunker_version,
            "chunk_index": chunk_index,
            "content_sha256": content_hash,
        }
        canonical = json.dumps(identity_payload, sort_keys=True, separators=(",", ":"))
        prepared.append((sha256(canonical.encode()).hexdigest(), item))

    chunks: list[GoldChunk] = []
    contributor_labels = tuple(
        (
            f"{contributor.label} ({', '.join(contributor.roles)})"
            if contributor.roles
            else contributor.label
        )
        for contributor in work.contributors
    )
    if work.licence_id is None or work.licence_url is None:
        raise ChunkingError(f"work {work.work_id} has incomplete licence provenance")
    page_lookup = {page.page_id: page for page in ordered_pages}
    for chunk_index, (chunk_id, item) in enumerate(prepared):
        quality_flags = tuple(
            sorted(
                {
                    flag.value
                    for span in item.page_spans
                    for flag in page_lookup[span.page_id].quality_flags
                }
            )
        )
        chunks.append(
            GoldChunk(
                gold_dataset_id=gold_dataset_id,
                silver_dataset_id=work.dataset_id,
                chunk_id=chunk_id,
                profile_id=config.profile_id,
                chunker_version=config.chunker_version,
                chunk_index=chunk_index,
                work_id=work.work_id,
                title=work.title,
                contributors=contributor_labels,
                production_dates=work.production_dates,
                production_labels=work.production_labels,
                subjects=work.subjects,
                genres=work.genres,
                language_id=config.eligible_language_id,
                licence_id=work.licence_id,
                licence_url=work.licence_url,
                source_url=work.source_url,
                iiif_manifest_url=work.iiif_manifest_url,
                text=item.text,
                content_sha256=sha256(item.text.encode()).hexdigest(),
                token_count=item.token_count,
                maximum_token_count=config.maximum_token_count,
                page_sequence_start=item.page_spans[0].sequence_number,
                page_sequence_end=item.page_spans[-1].sequence_number,
                page_label_start=item.page_spans[0].page_label,
                page_label_end=item.page_spans[-1].page_label,
                page_spans=item.page_spans,
                overlap_previous_token_count=item.overlap_token_count,
                overlap_prefix_char_end=item.overlap_prefix_char_end,
                previous_chunk_id=prepared[chunk_index - 1][0]
                if chunk_index > 0
                else None,
                next_chunk_id=prepared[chunk_index + 1][0]
                if chunk_index + 1 < len(prepared)
                else None,
                inherited_quality_flags=quality_flags,
            )
        )
    return tuple(chunks)


def _page_fragments(
    page: SilverPage,
    config: ChunkingConfig,
    tokenizer: TokenBoundary,
) -> tuple[_Fragment, ...]:
    """Split one page at structural gaps, then at hard tokenizer limits."""

    text = page.clean_text
    structural_spans: list[tuple[int, int]] = []
    start = 0
    for match in _STRUCTURAL_GAP.finditer(text):
        end = match.start()
        if text[start:end].strip():
            structural_spans.append((start, end))
        start = match.end()
    if text[start:].strip():
        structural_spans.append((start, len(text)))
    if not structural_spans and text.strip():
        structural_spans.append((0, len(text)))

    fragments: list[_Fragment] = []
    fragment_limit = config.maximum_token_count - config.overlap_token_count
    for span_start, span_end in structural_spans:
        source_text = text[span_start:span_end]
        for token_span in tokenizer.split_to_model_limit(
            source_text,
            fragment_limit,
        ):
            fragments.append(
                _Fragment(
                    page=page,
                    text=token_span.text,
                    source_char_start=span_start + token_span.char_start,
                    source_char_end=span_start + token_span.char_end,
                )
            )
    return tuple(fragments)


def _chunk_fragment_run(
    fragments: tuple[_Fragment, ...],
    config: ChunkingConfig,
    tokenizer: TokenBoundary,
) -> tuple[_Draft, ...]:
    """Greedily accumulate one uninterrupted run of page fragments."""

    if not fragments:
        return ()
    drafts: list[_Draft] = []
    current: list[_Fragment] = []
    overlap_fragment_count = 0
    for fragment in fragments:
        if not current:
            current.append(fragment)
            continue
        candidate = _render_fragments(tuple((*current, fragment)))
        candidate_tokens = tokenizer.token_count(candidate[0])
        current_tokens = tokenizer.token_count(_render_fragments(tuple(current))[0])
        if (
            current_tokens < config.target_token_count
            and candidate_tokens <= config.maximum_token_count
        ):
            current.append(fragment)
            continue

        completed = _Draft(
            fragments=tuple(current),
            overlap_fragment_count=overlap_fragment_count,
        )
        drafts.append(completed)
        overlap = _trailing_overlap(
            completed.fragments,
            config.overlap_token_count,
            tokenizer,
        )
        current = [*overlap, fragment]
        overlap_fragment_count = len(overlap)
        if tokenizer.token_count(_render_fragments(tuple(current))[0]) > (
            config.maximum_token_count
        ):
            current = [fragment]
            overlap_fragment_count = 0

    drafts.append(
        _Draft(
            fragments=tuple(current),
            overlap_fragment_count=overlap_fragment_count,
        )
    )
    if len(drafts) >= 2:
        last = drafts[-1]
        last_rendered = _render_draft(last, tokenizer)
        if last_rendered.token_count < config.minimum_token_count:
            primary_tail = last.fragments[last.overlap_fragment_count :]
            merged = replace(
                drafts[-2],
                fragments=tuple((*drafts[-2].fragments, *primary_tail)),
            )
            if (
                tokenizer.token_count(_render_fragments(merged.fragments)[0])
                <= config.maximum_token_count
            ):
                drafts[-2] = merged
                drafts.pop()
    return tuple(drafts)


def _trailing_overlap(
    fragments: tuple[_Fragment, ...],
    requested_tokens: int,
    tokenizer: TokenBoundary,
) -> tuple[_Fragment, ...]:
    """Return tokenizer-aligned trailing fragments with page provenance."""

    if requested_tokens <= 0:
        return ()
    selected_reversed: list[_Fragment] = []
    remaining = requested_tokens
    for fragment in reversed(fragments):
        fragment_tokens = tokenizer.token_count(
            fragment.text,
            add_special_tokens=False,
        )
        if fragment_tokens <= remaining:
            selected_reversed.append(fragment)
            remaining -= fragment_tokens
        else:
            trailing = tokenizer.trailing_content(fragment.text, remaining)
            if trailing.text:
                selected_reversed.append(
                    _Fragment(
                        page=fragment.page,
                        text=trailing.text,
                        source_char_start=fragment.source_char_start
                        + trailing.char_start,
                        source_char_end=fragment.source_char_start + trailing.char_end,
                    )
                )
            remaining = 0
        if remaining <= 0:
            break
    return tuple(reversed(selected_reversed))


def _render_draft(
    draft: _Draft,
    tokenizer: TokenBoundary,
) -> _RenderedDraft:
    text, page_spans = _render_fragments(draft.fragments)
    overlap_text = ""
    if draft.overlap_fragment_count:
        overlap_text = _render_fragments(
            draft.fragments[: draft.overlap_fragment_count]
        )[0]
    return _RenderedDraft(
        text=text,
        page_spans=page_spans,
        token_count=tokenizer.token_count(text),
        overlap_token_count=tokenizer.token_count(
            overlap_text,
            add_special_tokens=False,
        )
        if overlap_text
        else 0,
        overlap_prefix_char_end=len(overlap_text),
    )


def _render_fragments(
    fragments: tuple[_Fragment, ...],
) -> tuple[str, tuple[ChunkPageSpan, ...]]:
    """Render fragments and calculate exact chunk-side page spans."""

    text = ""
    page_ranges: dict[str, _PageRange] = {}
    for index, fragment in enumerate(fragments):
        if index:
            previous = fragments[index - 1]
            text += " " if previous.page.page_id == fragment.page.page_id else "\n\n"
        chunk_start = len(text)
        text += fragment.text
        chunk_end = len(text)
        existing = page_ranges.get(fragment.page.page_id)
        if existing is None:
            page_ranges[fragment.page.page_id] = _PageRange(
                page=fragment.page,
                chunk_char_start=chunk_start,
                chunk_char_end=chunk_end,
                source_char_start=fragment.source_char_start,
                source_char_end=fragment.source_char_end,
            )
        else:
            existing.chunk_char_end = chunk_end
            existing.source_char_start = min(
                existing.source_char_start,
                fragment.source_char_start,
            )
            existing.source_char_end = max(
                existing.source_char_end,
                fragment.source_char_end,
            )

    spans = tuple(
        ChunkPageSpan(
            page_id=item.page.page_id,
            sequence_number=item.page.sequence_number,
            page_label=item.page.page_label,
            printed_page_number=item.page.printed_page_number,
            canvas_id=item.page.canvas_id,
            image_url=item.page.image_url,
            chunk_char_start=item.chunk_char_start,
            chunk_char_end=item.chunk_char_end,
            source_char_start=item.source_char_start,
            source_char_end=item.source_char_end,
        )
        for item in page_ranges.values()
    )
    return text, spans
