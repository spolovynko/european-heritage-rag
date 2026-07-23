"""Strict contracts for retrieval-ready Gold chunks and datasets."""

from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from typing import Literal, Self

from pydantic import (
    AnyHttpUrl,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

_SHA256_PATTERN = r"^[0-9a-f]{64}$"
_SAFE_IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]*$"


class GoldModel(BaseModel):
    """Base model for strict immutable Gold contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class HeaderFooterPolicy(StrEnum):
    """How Gold treats the header/footer decisions made by Silver."""

    USE_SILVER_CLEAN_TEXT = "use_silver_clean_text"


class GoldScope(StrEnum):
    """Whether a dataset covers all eligible works or one selected work."""

    FULL = "full"
    SELECTED_WORKS = "selected_works"


class ChunkingConfig(GoldModel):
    """Versioned tokenizer and chunk-boundary policy."""

    profile_id: str = Field(
        min_length=1,
        max_length=100,
        pattern=_SAFE_IDENTIFIER_PATTERN,
    )
    target_token_count: int = Field(ge=32)
    maximum_token_count: int = Field(ge=32)
    overlap_token_count: int = Field(ge=0)
    minimum_token_count: int = Field(ge=1)
    tokenizer_model: str = Field(min_length=1, max_length=200)
    tokenizer_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    tokenizer_maximum_length: int = Field(ge=1)
    count_special_tokens: bool = True
    input_text_field: Literal["clean_text"] = "clean_text"
    header_footer_policy: HeaderFooterPolicy = HeaderFooterPolicy.USE_SILVER_CLEAN_TEXT
    chunker_version: str = Field(min_length=1, max_length=100)
    eligible_language_id: str = Field(min_length=2, max_length=20)
    require_single_language: bool = True

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        """Reject unsafe or internally contradictory chunking limits."""

        if self.target_token_count > self.maximum_token_count:
            raise ValueError("target_token_count must not exceed maximum_token_count")
        if self.maximum_token_count > self.tokenizer_maximum_length:
            raise ValueError(
                "maximum_token_count must not exceed tokenizer_maximum_length"
            )
        if self.overlap_token_count >= self.target_token_count:
            raise ValueError("overlap_token_count must be smaller than target")
        if self.minimum_token_count >= self.target_token_count:
            raise ValueError("minimum_token_count must be smaller than target")
        return self


class ChunkPageSpan(GoldModel):
    """One contributing Silver page and its exact span inside a chunk."""

    page_id: str = Field(pattern=_SHA256_PATTERN)
    sequence_number: int = Field(ge=1)
    page_label: str = Field(min_length=1)
    printed_page_number: int | None = Field(default=None, ge=0)
    canvas_id: AnyHttpUrl
    image_url: AnyHttpUrl | None = None
    chunk_char_start: int = Field(ge=0)
    chunk_char_end: int = Field(ge=1)
    source_char_start: int = Field(ge=0)
    source_char_end: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_ranges(self) -> Self:
        """Require non-empty half-open character ranges."""

        if self.chunk_char_end <= self.chunk_char_start:
            raise ValueError("chunk character range must be non-empty")
        if self.source_char_end <= self.source_char_start:
            raise ValueError("source character range must be non-empty")
        return self


class GoldChunk(GoldModel):
    """One retrieval-ready passage with citation-safe page provenance."""

    schema_version: Literal[1] = 1
    gold_dataset_id: str = Field(pattern=_SHA256_PATTERN)
    silver_dataset_id: str = Field(pattern=_SHA256_PATTERN)
    chunk_id: str = Field(pattern=_SHA256_PATTERN)
    profile_id: str = Field(min_length=1, max_length=100)
    chunker_version: str = Field(min_length=1, max_length=100)
    chunk_index: int = Field(ge=0)
    work_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=_SAFE_IDENTIFIER_PATTERN,
    )
    title: str = Field(min_length=1)
    contributors: tuple[str, ...] = ()
    production_dates: tuple[str, ...] = ()
    production_labels: tuple[str, ...] = ()
    subjects: tuple[str, ...] = ()
    genres: tuple[str, ...] = ()
    language_id: str = Field(min_length=2, max_length=20)
    licence_id: str = Field(min_length=1)
    licence_url: AnyHttpUrl
    source_url: AnyHttpUrl
    iiif_manifest_url: AnyHttpUrl
    text: str = Field(min_length=1)
    content_sha256: str = Field(pattern=_SHA256_PATTERN)
    token_count: int = Field(ge=1)
    maximum_token_count: int = Field(ge=1)
    page_sequence_start: int = Field(ge=1)
    page_sequence_end: int = Field(ge=1)
    page_label_start: str = Field(min_length=1)
    page_label_end: str = Field(min_length=1)
    page_spans: tuple[ChunkPageSpan, ...] = Field(min_length=1)
    overlap_previous_token_count: int = Field(ge=0)
    overlap_prefix_char_end: int = Field(ge=0)
    previous_chunk_id: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    next_chunk_id: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    inherited_quality_flags: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_chunk_consistency(self) -> Self:
        """Keep text, token limits, page ranges, and adjacency coherent."""

        if not self.text.strip():
            raise ValueError("chunk text must contain non-whitespace characters")
        if sha256(self.text.encode()).hexdigest() != self.content_sha256:
            raise ValueError("content_sha256 must match chunk text")
        if self.token_count > self.maximum_token_count:
            raise ValueError("token_count must not exceed maximum_token_count")
        if self.page_sequence_end < self.page_sequence_start:
            raise ValueError("page sequence range must be ordered")
        if self.overlap_prefix_char_end > len(self.text):
            raise ValueError("overlap prefix must fall inside chunk text")
        if self.overlap_previous_token_count == 0 and self.overlap_prefix_char_end:
            raise ValueError("zero overlap cannot have a highlighted prefix")

        page_ids = tuple(span.page_id for span in self.page_spans)
        if len(set(page_ids)) != len(page_ids):
            raise ValueError("page_spans must contain unique pages")
        sequences = tuple(span.sequence_number for span in self.page_spans)
        if sequences != tuple(sorted(sequences)):
            raise ValueError("page_spans must follow source order")
        if sequences[0] != self.page_sequence_start:
            raise ValueError("page_sequence_start must match the first page span")
        if sequences[-1] != self.page_sequence_end:
            raise ValueError("page_sequence_end must match the last page span")
        if self.page_spans[0].page_label != self.page_label_start:
            raise ValueError("page_label_start must match the first page span")
        if self.page_spans[-1].page_label != self.page_label_end:
            raise ValueError("page_label_end must match the last page span")
        for span in self.page_spans:
            if span.chunk_char_end > len(self.text):
                raise ValueError("page span must fall inside chunk text")
        return self


class GoldExclusion(GoldModel):
    """One work or page omitted from retrieval chunks with an explicit reason."""

    kind: Literal["work", "page"]
    identifier: str = Field(min_length=1, max_length=128)
    reason: str = Field(min_length=1, max_length=500)


class GoldStatistics(GoldModel):
    """Measured output properties for one Gold dataset."""

    schema_version: Literal[1] = 1
    gold_dataset_id: str = Field(pattern=_SHA256_PATTERN)
    silver_dataset_id: str = Field(pattern=_SHA256_PATTERN)
    profile_id: str = Field(min_length=1, max_length=100)
    work_count: int = Field(ge=0)
    contributing_page_count: int = Field(ge=0)
    chunk_count: int = Field(ge=0)
    empty_chunk_count: int = Field(ge=0)
    short_chunk_count: int = Field(ge=0)
    minimum_tokens: int = Field(ge=0)
    mean_tokens: float = Field(ge=0)
    median_tokens: float = Field(ge=0)
    p95_tokens: float = Field(ge=0)
    maximum_tokens: int = Field(ge=0)
    mean_pages_per_chunk: float = Field(ge=0)
    maximum_pages_per_chunk: int = Field(ge=0)
    requested_overlap_tokens: int = Field(ge=0)
    actual_overlap_tokens: int = Field(ge=0)
    overlap_ratio: float = Field(ge=0, le=1)
    unique_source_tokens: int = Field(ge=0)
    emitted_tokens: int = Field(ge=0)
    output_token_inflation_ratio: float = Field(ge=0)
    language_counts: dict[str, int] = Field(default_factory=dict)
    exclusions: tuple[GoldExclusion, ...] = ()

    @model_validator(mode="after")
    def validate_chunk_counts(self) -> Self:
        """Require headline empty-chunk evidence to be honest."""

        if self.empty_chunk_count > self.chunk_count:
            raise ValueError("empty_chunk_count cannot exceed chunk_count")
        return self


class GoldFileRecord(GoldModel):
    """Integrity receipt for one file in a complete Gold dataset."""

    name: str = Field(min_length=1, max_length=200)
    byte_length: int = Field(ge=1)
    content_sha256: str = Field(pattern=_SHA256_PATTERN)


class GoldDatasetManifest(GoldModel):
    """Complete input, configuration, scope, and output ledger."""

    schema_version: Literal[1] = 1
    gold_dataset_id: str = Field(pattern=_SHA256_PATTERN)
    silver_dataset_id: str = Field(pattern=_SHA256_PATTERN)
    silver_manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    gold_schema_version: Literal[1] = 1
    chunking_config: ChunkingConfig
    scope: GoldScope
    selected_work_ids: tuple[str, ...] = ()
    pipeline_version: str = Field(min_length=1, max_length=100)
    generated_at: AwareDatetime
    work_count: int = Field(ge=0)
    contributing_page_count: int = Field(ge=0)
    chunk_count: int = Field(ge=0)
    files: tuple[GoldFileRecord, ...] = Field(min_length=3)

    @model_validator(mode="after")
    def validate_manifest(self) -> Self:
        """Require a coherent scope and complete output inventory."""

        if self.scope is GoldScope.FULL and self.selected_work_ids:
            raise ValueError("full scope must not declare selected_work_ids")
        if self.scope is GoldScope.SELECTED_WORKS and not self.selected_work_ids:
            raise ValueError("selected scope requires selected_work_ids")
        if len(set(self.selected_work_ids)) != len(self.selected_work_ids):
            raise ValueError("selected_work_ids must be unique")
        names = tuple(record.name for record in self.files)
        if len(set(names)) != len(names):
            raise ValueError("Gold file names must be unique")
        required = {"chunks.parquet", "statistics.json", "statistics.md"}
        if not required.issubset(names):
            raise ValueError("Gold manifest is missing a required output file")
        return self


class GoldValidationIssue(GoldModel):
    """One actionable integrity, schema, or provenance problem."""

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    filename: str | None = None


class GoldValidationReport(GoldModel):
    """Machine-readable offline validation result."""

    gold_dataset_id: str = Field(pattern=_SHA256_PATTERN)
    issues: tuple[GoldValidationIssue, ...] = ()

    @property
    def is_valid(self) -> bool:
        """Return whether every Gold check passed."""

        return not self.issues


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp at the publication boundary."""

    return datetime.now(UTC)
