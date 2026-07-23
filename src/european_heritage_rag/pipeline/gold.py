"""Validated Silver-to-Gold transformation and chunk statistics."""

import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import sha256
from statistics import fmean, median
from typing import Final, Literal

from european_heritage_rag.domain.gold import (
    ChunkingConfig,
    GoldChunk,
    GoldExclusion,
    GoldScope,
    GoldStatistics,
)
from european_heritage_rag.domain.silver import (
    SilverDatasetManifest,
    SilverPage,
)
from european_heritage_rag.pipeline.chunking import (
    GOLD_SCHEMA_VERSION,
    ChunkingError,
    chunk_work,
)
from european_heritage_rag.pipeline.silver_store import (
    SilverFilesystemStore,
    validate_silver_dataset,
)
from european_heritage_rag.pipeline.tokenization import TokenBoundary

GOLD_PIPELINE_VERSION: Final[Literal["gold-pipeline-v1"]] = "gold-pipeline-v1"


class GoldTransformError(RuntimeError):
    """Raised when a Silver dataset cannot become trustworthy Gold chunks."""


@dataclass(frozen=True, slots=True)
class GoldTransformResult:
    """Gold rows, statistics, and deterministic publication identity."""

    gold_dataset_id: str
    silver_dataset_id: str
    silver_manifest_sha256: str
    config: ChunkingConfig
    scope: GoldScope
    selected_work_ids: tuple[str, ...]
    chunks: tuple[GoldChunk, ...]
    statistics: GoldStatistics


def gold_dataset_id(
    silver_manifest: SilverDatasetManifest,
    silver_manifest_sha256: str,
    config: ChunkingConfig,
    *,
    selected_work_ids: tuple[str, ...] = (),
) -> str:
    """Derive one stable identity from parent evidence, rules, and scope."""

    payload = {
        "silver_dataset_id": silver_manifest.dataset_id,
        "silver_manifest_sha256": silver_manifest_sha256,
        "gold_schema_version": GOLD_SCHEMA_VERSION,
        "pipeline_version": GOLD_PIPELINE_VERSION,
        "chunking_config": config.model_dump(mode="json"),
        "selected_work_ids": sorted(selected_work_ids),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode()).hexdigest()


def transform_silver_dataset(
    store: SilverFilesystemStore,
    manifest: SilverDatasetManifest,
    *,
    config: ChunkingConfig,
    tokenizer: TokenBoundary,
    selected_work_ids: tuple[str, ...] = (),
) -> GoldTransformResult:
    """Create one deterministic Gold experiment entirely from validated Silver."""

    validation = validate_silver_dataset(store, manifest)
    if not validation.is_valid:
        codes = ", ".join(issue.code for issue in validation.issues)
        raise GoldTransformError(f"Silver validation failed: {codes}")
    if tokenizer.model_id != config.tokenizer_model:
        raise GoldTransformError("loaded tokenizer model differs from configuration")
    if tokenizer.revision != config.tokenizer_revision:
        raise GoldTransformError("loaded tokenizer revision differs from configuration")
    if tokenizer.model_maximum_length != config.tokenizer_maximum_length:
        raise GoldTransformError("loaded tokenizer maximum differs from configuration")

    manifest_path = store.manifest_path(manifest.dataset_id)
    manifest_hash = sha256(manifest_path.read_bytes()).hexdigest()
    selected = tuple(sorted(set(selected_work_ids)))
    scope = GoldScope.SELECTED_WORKS if selected else GoldScope.FULL
    dataset_id = gold_dataset_id(
        manifest,
        manifest_hash,
        config,
        selected_work_ids=selected,
    )

    works = store.read_works(manifest.dataset_id)
    pages = store.read_pages(manifest.dataset_id)
    known_work_ids = {work.work_id for work in works}
    unknown = sorted(set(selected) - known_work_ids)
    if unknown:
        raise GoldTransformError(f"selected Silver works do not exist: {unknown}")
    scoped_works = tuple(
        work for work in works if not selected or work.work_id in selected
    )
    pages_by_work: dict[str, list[SilverPage]] = defaultdict(list)
    for page in pages:
        pages_by_work[page.work_id].append(page)

    chunks: list[GoldChunk] = []
    exclusions: list[GoldExclusion] = []
    eligible_pages: list[SilverPage] = []
    language_counts: Counter[str] = Counter()
    contributing_work_ids: set[str] = set()
    for work in scoped_works:
        if work.language_ids != (config.eligible_language_id,):
            exclusions.append(
                GoldExclusion(
                    kind="work",
                    identifier=work.work_id,
                    reason=(
                        "Gold v1 requires exactly one work-level language "
                        f"({config.eligible_language_id}); found "
                        f"{list(work.language_ids) or ['unknown']}"
                    ),
                )
            )
            continue
        if work.licence_id is None or work.licence_url is None:
            exclusions.append(
                GoldExclusion(
                    kind="work",
                    identifier=work.work_id,
                    reason="required licence provenance is incomplete",
                )
            )
            continue
        work_pages = tuple(
            sorted(
                pages_by_work[work.work_id],
                key=lambda item: item.sequence_number,
            )
        )
        for page in work_pages:
            if page.clean_text.strip():
                eligible_pages.append(page)
            else:
                exclusions.append(
                    GoldExclusion(
                        kind="page",
                        identifier=page.page_id,
                        reason=(
                            "Silver clean_text is empty; page is a hard chunk boundary"
                        ),
                    )
                )
        try:
            work_chunks = chunk_work(
                work,
                work_pages,
                gold_dataset_id=dataset_id,
                config=config,
                tokenizer=tokenizer,
            )
        except ChunkingError as error:
            raise GoldTransformError(str(error)) from error
        if work_chunks:
            contributing_work_ids.add(work.work_id)
            language_counts.update((config.eligible_language_id,))
            chunks.extend(work_chunks)

    chunks_tuple = tuple(
        sorted(chunks, key=lambda item: (item.work_id, item.chunk_index))
    )
    chunk_ids = tuple(chunk.chunk_id for chunk in chunks_tuple)
    if len(set(chunk_ids)) != len(chunk_ids):
        raise GoldTransformError("chunk IDs are not unique")
    contributing_page_ids = {
        span.page_id for chunk in chunks_tuple for span in chunk.page_spans
    }
    missing_page_ids = {page.page_id for page in eligible_pages} - contributing_page_ids
    if missing_page_ids:
        raise GoldTransformError(
            "eligible Silver pages are missing from Gold provenance: "
            f"{sorted(missing_page_ids)}"
        )

    token_counts = [chunk.token_count for chunk in chunks_tuple]
    pages_per_chunk = [len(chunk.page_spans) for chunk in chunks_tuple]
    actual_overlap = sum(chunk.overlap_previous_token_count for chunk in chunks_tuple)
    emitted_tokens = sum(token_counts)
    unique_source_tokens = sum(
        tokenizer.token_count(page.clean_text, add_special_tokens=False)
        for page in eligible_pages
    )
    statistics = GoldStatistics(
        gold_dataset_id=dataset_id,
        silver_dataset_id=manifest.dataset_id,
        profile_id=config.profile_id,
        work_count=len(contributing_work_ids),
        contributing_page_count=len(contributing_page_ids),
        chunk_count=len(chunks_tuple),
        empty_chunk_count=sum(not chunk.text.strip() for chunk in chunks_tuple),
        short_chunk_count=sum(
            chunk.token_count < config.minimum_token_count for chunk in chunks_tuple
        ),
        minimum_tokens=min(token_counts, default=0),
        mean_tokens=fmean(token_counts) if token_counts else 0.0,
        median_tokens=median(token_counts) if token_counts else 0.0,
        p95_tokens=_percentile(token_counts, 0.95),
        maximum_tokens=max(token_counts, default=0),
        mean_pages_per_chunk=fmean(pages_per_chunk) if pages_per_chunk else 0.0,
        maximum_pages_per_chunk=max(pages_per_chunk, default=0),
        requested_overlap_tokens=config.overlap_token_count,
        actual_overlap_tokens=actual_overlap,
        overlap_ratio=(actual_overlap / emitted_tokens if emitted_tokens else 0.0),
        unique_source_tokens=unique_source_tokens,
        emitted_tokens=emitted_tokens,
        output_token_inflation_ratio=(
            max(0.0, (emitted_tokens - unique_source_tokens) / unique_source_tokens)
            if unique_source_tokens
            else 0.0
        ),
        language_counts=dict(sorted(language_counts.items())),
        exclusions=tuple(exclusions),
    )
    return GoldTransformResult(
        gold_dataset_id=dataset_id,
        silver_dataset_id=manifest.dataset_id,
        silver_manifest_sha256=manifest_hash,
        config=config,
        scope=scope,
        selected_work_ids=selected,
        chunks=chunks_tuple,
        statistics=statistics,
    )


def _percentile(values: list[int], fraction: float) -> float:
    """Return a deterministic nearest-rank percentile."""

    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(fraction * len(ordered)))
    return float(ordered[rank - 1])
