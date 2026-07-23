"""Parquet persistence, atomic publication, and validation for Silver."""

import os
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from uuid import uuid4

import polars as pl
import pyarrow.parquet as pq  # type: ignore[import-untyped]
from polars._typing import SchemaDict
from pydantic import ValidationError

from european_heritage_rag.domain.silver import (
    SilverDatasetManifest,
    SilverFileRecord,
    SilverPage,
    SilverQualityReport,
    SilverValidationIssue,
    SilverValidationReport,
    SilverWork,
    utc_now,
)
from european_heritage_rag.pipeline.bronze_store import sha256_hex
from european_heritage_rag.pipeline.silver import (
    CLEANING_VERSION,
    HEADER_FOOTER_VERSION,
    QUALITY_VERSION,
    SILVER_SCHEMA_VERSION,
    SilverTransformResult,
)

_DISTRIBUTION_NAME = "european-heritage-rag"

_LINEAGE_DTYPE = pl.List(
    pl.Struct(
        {
            "resource_id": pl.String,
            "resource_type": pl.String,
            "relative_path": pl.String,
            "source_url": pl.String,
            "content_sha256": pl.String,
        }
    )
)
_CONTRIBUTOR_DTYPE = pl.List(
    pl.Struct(
        {
            "agent_id": pl.String,
            "label": pl.String,
            "roles": pl.List(pl.String),
            "primary": pl.Boolean,
        }
    )
)
WORKS_SCHEMA_DEFINITION: SchemaDict = {
    "schema_version": pl.Int64,
    "dataset_id": pl.String,
    "work_id": pl.String,
    "title": pl.String,
    "alternative_titles": pl.List(pl.String),
    "contributors": _CONTRIBUTOR_DTYPE,
    "production_dates": pl.List(pl.String),
    "production_labels": pl.List(pl.String),
    "subjects": pl.List(pl.String),
    "genres": pl.List(pl.String),
    "language_ids": pl.List(pl.String),
    "language_labels": pl.List(pl.String),
    "licence_id": pl.String,
    "licence_url": pl.String,
    "source_url": pl.String,
    "iiif_manifest_url": pl.String,
    "source_content_sha256": pl.String,
    "iiif_manifest_content_sha256": pl.String,
    "quality_flags": pl.List(pl.String),
    "lineage": _LINEAGE_DTYPE,
}
PAGES_SCHEMA_DEFINITION: SchemaDict = {
    "schema_version": pl.Int64,
    "dataset_id": pl.String,
    "page_id": pl.String,
    "work_id": pl.String,
    "canvas_id": pl.String,
    "sequence_number": pl.Int64,
    "page_label": pl.String,
    "printed_page_number": pl.Int64,
    "raw_text": pl.String,
    "clean_text": pl.String,
    "detected_headers": pl.List(pl.String),
    "detected_footers": pl.List(pl.String),
    "ocr_quality": pl.String,
    "quality_flags": pl.List(pl.String),
    "raw_line_count": pl.Int64,
    "raw_word_count": pl.Int64,
    "clean_word_count": pl.Int64,
    "cleaning_change_ratio": pl.Float64,
    "image_url": pl.String,
    "image_service_url": pl.String,
    "annotation_urls": pl.List(pl.String),
    "lineage": _LINEAGE_DTYPE,
}
WORKS_SCHEMA = pl.Schema(WORKS_SCHEMA_DEFINITION)
PAGES_SCHEMA = pl.Schema(PAGES_SCHEMA_DEFINITION)


class SilverContentConflictError(RuntimeError):
    """Raised when an existing complete dataset disagrees with its identity."""


@dataclass(frozen=True, slots=True)
class SilverBuildResult:
    """Published manifest and whether it was newly created."""

    manifest: SilverDatasetManifest
    created: bool


class SilverFilesystemStore:
    """Store complete deterministic Silver datasets on a local filesystem."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def dataset_directory(self, dataset_id: str) -> Path:
        """Return one dataset directory beneath the configured root."""

        return self.root / "wellcome" / f"dataset_id={dataset_id}"

    def manifest_path(self, dataset_id: str) -> Path:
        """Return the completeness marker for one dataset."""

        return self.dataset_directory(dataset_id) / "silver-manifest.json"

    def publish(
        self,
        result: SilverTransformResult,
        *,
        pipeline_version: str | None = None,
    ) -> SilverBuildResult:
        """Write, validate, and publish a complete Silver dataset."""

        existing = self.load_manifest(result.dataset_id)
        if existing is not None:
            report = validate_silver_dataset(self, existing)
            if not report.is_valid:
                raise SilverContentConflictError(
                    "existing Silver dataset is invalid: "
                    + ", ".join(issue.code for issue in report.issues)
                )
            if existing.bronze_inventory_sha256 != result.bronze_inventory_sha256:
                raise SilverContentConflictError(
                    "existing Silver dataset has different Bronze inventory"
                )
            return SilverBuildResult(manifest=existing, created=False)

        directory = self.dataset_directory(result.dataset_id)
        directory.mkdir(parents=True, exist_ok=True)
        works_path = directory / "works.parquet"
        pages_path = directory / "pages.parquet"
        quality_json_path = directory / "quality-report.json"
        quality_markdown_path = directory / "quality-report.md"

        self._write_parquet_atomically(
            works_path,
            _frame_from_models(result.works, WORKS_SCHEMA),
        )
        self._write_parquet_atomically(
            pages_path,
            _frame_from_models(result.pages, PAGES_SCHEMA),
        )
        self._write_bytes_atomically(
            quality_json_path,
            f"{result.quality_report.model_dump_json(indent=2)}\n".encode(),
        )
        self._write_bytes_atomically(
            quality_markdown_path,
            _quality_markdown(result.quality_report).encode(),
        )

        files = tuple(
            _file_record(path)
            for path in (
                works_path,
                pages_path,
                quality_json_path,
                quality_markdown_path,
            )
        )
        manifest = SilverDatasetManifest(
            dataset_id=result.dataset_id,
            bronze_run_id=result.bronze_run_id,
            bronze_inventory_sha256=result.bronze_inventory_sha256,
            silver_schema_version=SILVER_SCHEMA_VERSION,
            cleaning_version=CLEANING_VERSION,
            header_footer_version=HEADER_FOOTER_VERSION,
            quality_version=QUALITY_VERSION,
            pipeline_version=pipeline_version or version(_DISTRIBUTION_NAME),
            generated_at=utc_now(),
            work_count=len(result.works),
            page_count=len(result.pages),
            files=files,
        )
        self._write_bytes_atomically(
            self.manifest_path(result.dataset_id),
            f"{manifest.model_dump_json(indent=2)}\n".encode(),
        )
        validation = validate_silver_dataset(self, manifest)
        if not validation.is_valid:
            raise RuntimeError(
                "published Silver dataset failed validation: "
                + ", ".join(issue.code for issue in validation.issues)
            )
        return SilverBuildResult(manifest=manifest, created=True)

    def load_manifest(self, dataset_id: str) -> SilverDatasetManifest | None:
        """Load one manifest when its completeness marker exists."""

        path = self.manifest_path(dataset_id)
        if not path.is_file():
            return None
        manifest = SilverDatasetManifest.model_validate_json(path.read_bytes())
        if manifest.dataset_id != dataset_id:
            raise ValueError("Silver manifest identity does not match its directory")
        return manifest

    def manifest_paths(self) -> tuple[Path, ...]:
        """Return complete Silver manifest paths in stable order."""

        pattern = "wellcome/dataset_id=*/silver-manifest.json"
        return tuple(sorted(path for path in self.root.glob(pattern) if path.is_file()))

    def list_manifests(self) -> tuple[SilverDatasetManifest, ...]:
        """Load complete datasets newest first."""

        manifests = [
            SilverDatasetManifest.model_validate_json(path.read_bytes())
            for path in self.manifest_paths()
        ]
        return tuple(
            sorted(manifests, key=lambda item: item.generated_at, reverse=True)
        )

    def find_manifest(self, dataset_id: str) -> SilverDatasetManifest | None:
        """Find a complete dataset by deterministic ID."""

        return self.load_manifest(dataset_id)

    def read_works(self, dataset_id: str) -> tuple[SilverWork, ...]:
        """Read and validate canonical Works from Parquet."""

        path = self.dataset_directory(dataset_id) / "works.parquet"
        return tuple(
            SilverWork.model_validate(row) for row in pl.read_parquet(path).to_dicts()
        )

    def read_pages(self, dataset_id: str) -> tuple[SilverPage, ...]:
        """Read and validate canonical Pages from Parquet."""

        path = self.dataset_directory(dataset_id) / "pages.parquet"
        return tuple(
            SilverPage.model_validate(row) for row in pl.read_parquet(path).to_dicts()
        )

    def read_quality(self, dataset_id: str) -> SilverQualityReport:
        """Read and validate machine-readable quality evidence."""

        path = self.dataset_directory(dataset_id) / "quality-report.json"
        return SilverQualityReport.model_validate_json(path.read_bytes())

    def _write_parquet_atomically(self, destination: Path, frame: pl.DataFrame) -> None:
        temporary = _temporary_path(destination)
        try:
            frame.write_parquet(
                temporary,
                compression="zstd",
                statistics=True,
            )
            _sync_file(temporary)
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)

    def _write_bytes_atomically(self, destination: Path, content: bytes) -> None:
        temporary = _temporary_path(destination)
        try:
            with temporary.open("xb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)


def validate_silver_dataset(
    store: SilverFilesystemStore,
    manifest: SilverDatasetManifest,
) -> SilverValidationReport:
    """Validate files, hashes, Parquet schemas, rows, and relationships."""

    issues: list[SilverValidationIssue] = []
    directory = store.dataset_directory(manifest.dataset_id)
    for record in manifest.files:
        path = directory / record.name
        if not path.is_file():
            issues.append(
                SilverValidationIssue(
                    code="missing_file",
                    message="Manifest-declared Silver file is missing",
                    filename=record.name,
                )
            )
            continue
        content = path.read_bytes()
        if len(content) != record.byte_length:
            issues.append(
                SilverValidationIssue(
                    code="byte_length_mismatch",
                    message="Silver file byte length differs from its receipt",
                    filename=record.name,
                )
            )
        if sha256_hex(content) != record.content_sha256:
            issues.append(
                SilverValidationIssue(
                    code="content_hash_mismatch",
                    message="Silver file SHA-256 differs from its receipt",
                    filename=record.name,
                )
            )

    for path in directory.glob("*.tmp"):
        issues.append(
            SilverValidationIssue(
                code="temporary_file",
                message="Incomplete Silver temporary file remains",
                filename=path.name,
            )
        )

    works: tuple[SilverWork, ...] = ()
    pages: tuple[SilverPage, ...] = ()
    try:
        _validate_parquet_schema(directory / "works.parquet", WORKS_SCHEMA)
        works = store.read_works(manifest.dataset_id)
    except (OSError, ValueError, ValidationError, pl.exceptions.PolarsError) as error:
        issues.append(
            SilverValidationIssue(
                code="invalid_works_parquet",
                message=str(error),
                filename="works.parquet",
            )
        )
    try:
        _validate_parquet_schema(directory / "pages.parquet", PAGES_SCHEMA)
        pages = store.read_pages(manifest.dataset_id)
    except (OSError, ValueError, ValidationError, pl.exceptions.PolarsError) as error:
        issues.append(
            SilverValidationIssue(
                code="invalid_pages_parquet",
                message=str(error),
                filename="pages.parquet",
            )
        )

    if works:
        work_ids = [work.work_id for work in works]
        if len(set(work_ids)) != len(work_ids):
            issues.append(
                SilverValidationIssue(
                    code="duplicate_work_id",
                    message="Work IDs must be unique",
                    filename="works.parquet",
                )
            )
        if len(works) != manifest.work_count:
            issues.append(
                SilverValidationIssue(
                    code="work_count_mismatch",
                    message="Manifest work count does not match Parquet",
                    filename="works.parquet",
                )
            )
    if pages:
        page_ids = [page.page_id for page in pages]
        if len(set(page_ids)) != len(page_ids):
            issues.append(
                SilverValidationIssue(
                    code="duplicate_page_id",
                    message="Page IDs must be unique",
                    filename="pages.parquet",
                )
            )
        known_work_ids = {work.work_id for work in works}
        unknown = sorted({page.work_id for page in pages} - known_work_ids)
        if unknown:
            issues.append(
                SilverValidationIssue(
                    code="unknown_page_work",
                    message=f"Pages reference unknown works: {unknown}",
                    filename="pages.parquet",
                )
            )
        if len(pages) != manifest.page_count:
            issues.append(
                SilverValidationIssue(
                    code="page_count_mismatch",
                    message="Manifest page count does not match Parquet",
                    filename="pages.parquet",
                )
            )

    try:
        quality = store.read_quality(manifest.dataset_id)
        if (
            quality.dataset_id != manifest.dataset_id
            or quality.work_count != manifest.work_count
            or quality.page_count != manifest.page_count
        ):
            issues.append(
                SilverValidationIssue(
                    code="quality_count_mismatch",
                    message="Quality report does not match manifest counts",
                    filename="quality-report.json",
                )
            )
    except (OSError, ValidationError) as error:
        issues.append(
            SilverValidationIssue(
                code="invalid_quality_report",
                message=str(error),
                filename="quality-report.json",
            )
        )

    return SilverValidationReport(
        dataset_id=manifest.dataset_id,
        issues=tuple(issues),
    )


def _frame_from_models(
    models: tuple[SilverWork, ...] | tuple[SilverPage, ...],
    schema: pl.Schema,
) -> pl.DataFrame:
    rows = [model.model_dump(mode="json") for model in models]
    return pl.DataFrame(rows, schema=schema, strict=True)


def _validate_parquet_schema(
    path: Path,
    expected: pl.Schema,
) -> None:
    """Require both Polars and PyArrow to see the exact field names."""

    polars_schema = pl.read_parquet_schema(path)
    if polars_schema != expected:
        raise ValueError(
            f"unexpected Polars schema: {polars_schema}; expected {expected}"
        )
    arrow_schema = pq.read_schema(path)
    if arrow_schema.names != list(expected):
        raise ValueError(f"unexpected PyArrow fields: {arrow_schema.names}")


def _file_record(path: Path) -> SilverFileRecord:
    content = path.read_bytes()
    return SilverFileRecord(
        name=path.name,
        byte_length=len(content),
        content_sha256=sha256_hex(content),
    )


def _temporary_path(destination: Path) -> Path:
    return destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")


def _sync_file(path: Path) -> None:
    with path.open("r+b") as stream:
        os.fsync(stream.fileno())


def _quality_markdown(report: SilverQualityReport) -> str:
    flag_lines = (
        "\n".join(
            f"- `{flag}`: {count}" for flag, count in report.page_flag_counts.items()
        )
        or "- None"
    )
    work_lines = "\n".join(
        (
            f"- `{work.work_id}`: {work.page_count} pages, "
            f"{work.empty_page_count} empty, "
            f"{work.review_page_count} needing review, "
            f"{work.average_clean_word_count:.1f} average clean words"
        )
        for work in report.works
    )
    return (
        "# Silver data quality report\n\n"
        f"- Dataset ID: `{report.dataset_id}`\n"
        f"- Works: {report.work_count}\n"
        f"- Pages: {report.page_count}\n"
        f"- Empty OCR pages: {report.empty_page_count}\n"
        f"- Pages needing review: {report.review_page_count}\n"
        f"- Usable pages: {report.usable_page_count}\n"
        f"- Average clean words per page: "
        f"{report.average_clean_word_count:.1f}\n\n"
        "The quality bands are deterministic review aids, not measured OCR "
        "accuracy.\n\n"
        "## Page flags\n\n"
        f"{flag_lines}\n\n"
        "## Work summaries\n\n"
        f"{work_lines}\n"
    )
