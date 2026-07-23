"""Canonical contracts for Silver works, pages, lineage, and quality."""

from datetime import datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import (
    AnyHttpUrl,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from european_heritage_rag.pipeline.bronze import BronzeResourceType

_SHA256_PATTERN = r"^[0-9a-f]{64}$"
_SAFE_IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]*$"


class SilverModel(BaseModel):
    """Base model for strict immutable Silver contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class OcrQualityBand(StrEnum):
    """Broad review category, not a claim of measured OCR accuracy."""

    MISSING = "missing"
    NEEDS_REVIEW = "needs_review"
    USABLE = "usable"


class PageQualityFlag(StrEnum):
    """Explainable page-level data and cleaning observations."""

    EMPTY_OCR = "empty_ocr"
    VERY_SHORT_TEXT = "very_short_text"
    HIGH_SYMBOL_RATIO = "high_symbol_ratio"
    HTML_REMOVED = "html_removed"
    DEHYPHENATION_APPLIED = "dehyphenation_applied"
    HEADER_DETECTED = "header_detected"
    FOOTER_DETECTED = "footer_detected"
    MISSING_PAGE_LABEL = "missing_page_label"
    DUPLICATE_PAGE_LABEL = "duplicate_page_label"
    MULTIPLE_ANNOTATION_LISTS = "multiple_annotation_lists"
    NON_TEXT_ANNOTATIONS = "non_text_annotations"
    MISSING_IMAGE = "missing_image"
    LARGE_CLEANING_CHANGE = "large_cleaning_change"


class WorkQualityFlag(StrEnum):
    """Explainable missing or incomplete canonical work metadata."""

    MISSING_CONTRIBUTORS = "missing_contributors"
    MISSING_PRODUCTION = "missing_production"
    MISSING_SUBJECTS = "missing_subjects"
    MISSING_GENRES = "missing_genres"
    MISSING_LANGUAGE = "missing_language"
    MISSING_LICENCE = "missing_licence"


class SilverLineage(SilverModel):
    """Exact Bronze resource receipt used by one Silver row."""

    resource_id: str = Field(min_length=1, max_length=512)
    resource_type: BronzeResourceType
    relative_path: str = Field(min_length=1, max_length=1024)
    source_url: AnyHttpUrl
    content_sha256: str = Field(pattern=_SHA256_PATTERN)


class SilverContributor(SilverModel):
    """Canonical contributor label and role information."""

    agent_id: str | None = Field(default=None, min_length=1, max_length=256)
    label: str = Field(min_length=1)
    roles: tuple[str, ...] = ()
    primary: bool = False


class SilverWork(SilverModel):
    """One canonical work shared by all of its page rows."""

    schema_version: Literal[1] = 1
    dataset_id: str = Field(pattern=_SHA256_PATTERN)
    work_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=_SAFE_IDENTIFIER_PATTERN,
    )
    title: str = Field(min_length=1)
    alternative_titles: tuple[str, ...] = ()
    contributors: tuple[SilverContributor, ...] = ()
    production_dates: tuple[str, ...] = ()
    production_labels: tuple[str, ...] = ()
    subjects: tuple[str, ...] = ()
    genres: tuple[str, ...] = ()
    language_ids: tuple[str, ...] = ()
    language_labels: tuple[str, ...] = ()
    licence_id: str | None = Field(default=None, min_length=1)
    licence_url: AnyHttpUrl | None = None
    source_url: AnyHttpUrl
    iiif_manifest_url: AnyHttpUrl
    source_content_sha256: str = Field(pattern=_SHA256_PATTERN)
    iiif_manifest_content_sha256: str = Field(pattern=_SHA256_PATTERN)
    quality_flags: tuple[WorkQualityFlag, ...] = ()
    lineage: tuple[SilverLineage, ...] = Field(min_length=2)

    @model_validator(mode="after")
    def validate_unique_values(self) -> Self:
        """Reject duplicate canonical values and lineage receipts."""

        _require_unique(self.alternative_titles, "alternative_titles")
        _require_unique(self.production_dates, "production_dates")
        _require_unique(self.subjects, "subjects")
        _require_unique(self.genres, "genres")
        _require_unique(self.language_ids, "language_ids")
        _require_unique(
            tuple(item.resource_id for item in self.lineage),
            "lineage resource IDs",
        )
        _require_unique(
            tuple(flag.value for flag in self.quality_flags),
            "quality flags",
        )
        return self


class SilverPage(SilverModel):
    """One canonical page-like IIIF canvas and its OCR views."""

    schema_version: Literal[1] = 1
    dataset_id: str = Field(pattern=_SHA256_PATTERN)
    page_id: str = Field(pattern=_SHA256_PATTERN)
    work_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=_SAFE_IDENTIFIER_PATTERN,
    )
    canvas_id: AnyHttpUrl
    sequence_number: int = Field(ge=1)
    page_label: str = Field(min_length=1)
    printed_page_number: int | None = Field(default=None, ge=0)
    raw_text: str
    clean_text: str
    detected_headers: tuple[str, ...] = ()
    detected_footers: tuple[str, ...] = ()
    ocr_quality: OcrQualityBand
    quality_flags: tuple[PageQualityFlag, ...] = ()
    raw_line_count: int = Field(ge=0)
    raw_word_count: int = Field(ge=0)
    clean_word_count: int = Field(ge=0)
    cleaning_change_ratio: float = Field(ge=0)
    image_url: AnyHttpUrl | None = None
    image_service_url: AnyHttpUrl | None = None
    annotation_urls: tuple[AnyHttpUrl, ...] = ()
    lineage: tuple[SilverLineage, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_page_consistency(self) -> Self:
        """Keep quality state, text counts, and lineage internally consistent."""

        if self.ocr_quality is OcrQualityBand.MISSING:
            if self.clean_text.strip():
                raise ValueError("missing OCR quality requires empty clean_text")
            if PageQualityFlag.EMPTY_OCR not in self.quality_flags:
                raise ValueError("missing OCR quality requires empty_ocr flag")
        elif not self.clean_text.strip():
            raise ValueError("non-missing OCR quality requires clean_text")

        _require_unique(
            tuple(flag.value for flag in self.quality_flags),
            "quality flags",
        )
        _require_unique(
            tuple(str(url) for url in self.annotation_urls),
            "annotation URLs",
        )
        _require_unique(
            tuple(item.resource_id for item in self.lineage),
            "lineage resource IDs",
        )
        return self


class SilverFileRecord(SilverModel):
    """Integrity receipt for one file in a complete Silver dataset."""

    name: str = Field(min_length=1, max_length=200)
    byte_length: int = Field(ge=1)
    content_sha256: str = Field(pattern=_SHA256_PATTERN)


class WorkQualitySummary(SilverModel):
    """Quality counts for one transformed work."""

    work_id: str = Field(min_length=1, max_length=128)
    page_count: int = Field(ge=0)
    empty_page_count: int = Field(ge=0)
    review_page_count: int = Field(ge=0)
    average_clean_word_count: float = Field(ge=0)


class SilverQualityReport(SilverModel):
    """Machine-readable aggregate quality evidence for one dataset."""

    schema_version: Literal[1] = 1
    dataset_id: str = Field(pattern=_SHA256_PATTERN)
    work_count: int = Field(ge=0)
    page_count: int = Field(ge=0)
    empty_page_count: int = Field(ge=0)
    review_page_count: int = Field(ge=0)
    usable_page_count: int = Field(ge=0)
    average_clean_word_count: float = Field(ge=0)
    language_counts: dict[str, int] = Field(default_factory=dict)
    page_flag_counts: dict[str, int] = Field(default_factory=dict)
    work_flag_counts: dict[str, int] = Field(default_factory=dict)
    processing_failures: tuple[str, ...] = ()
    works: tuple[WorkQualitySummary, ...] = ()

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        """Require headline totals to reconcile."""

        if (
            self.empty_page_count + self.review_page_count + self.usable_page_count
            != self.page_count
        ):
            raise ValueError("page quality counts must equal page_count")
        if len(self.works) != self.work_count:
            raise ValueError("work summaries must equal work_count")
        return self


class SilverDatasetManifest(SilverModel):
    """Complete identity, input, configuration, and output ledger."""

    schema_version: Literal[1] = 1
    dataset_id: str = Field(pattern=_SHA256_PATTERN)
    bronze_run_id: str = Field(min_length=1, max_length=128)
    bronze_inventory_sha256: str = Field(pattern=_SHA256_PATTERN)
    silver_schema_version: Literal[1] = 1
    cleaning_version: str = Field(min_length=1, max_length=100)
    header_footer_version: str = Field(min_length=1, max_length=100)
    quality_version: str = Field(min_length=1, max_length=100)
    pipeline_version: str = Field(min_length=1, max_length=100)
    generated_at: AwareDatetime
    work_count: int = Field(ge=0)
    page_count: int = Field(ge=0)
    files: tuple[SilverFileRecord, ...] = Field(min_length=4)

    @model_validator(mode="after")
    def validate_files(self) -> Self:
        """Require the complete declared Silver output inventory."""

        names = tuple(record.name for record in self.files)
        _require_unique(names, "Silver file names")
        required = {
            "works.parquet",
            "pages.parquet",
            "quality-report.json",
            "quality-report.md",
        }
        if not required.issubset(names):
            raise ValueError("Silver manifest is missing a required output file")
        return self


class SilverValidationIssue(SilverModel):
    """One actionable integrity or schema problem in a Silver dataset."""

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    filename: str | None = None


class SilverValidationReport(SilverModel):
    """Machine-readable offline validation result."""

    dataset_id: str = Field(pattern=_SHA256_PATTERN)
    issues: tuple[SilverValidationIssue, ...] = ()

    @property
    def is_valid(self) -> bool:
        """Return whether every Silver check passed."""

        return not self.issues


def _require_unique(values: tuple[object, ...], field_name: str) -> None:
    """Raise a validation error when a canonical sequence contains duplicates."""

    if len(set(values)) != len(values):
        raise ValueError(f"{field_name} must be unique")


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp at the application boundary."""

    from datetime import UTC

    return datetime.now(UTC)
