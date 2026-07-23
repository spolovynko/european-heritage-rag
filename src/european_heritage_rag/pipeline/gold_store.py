"""Parquet persistence, atomic publication, and validation for Gold."""

import os
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from uuid import uuid4

import polars as pl
import pyarrow.parquet as pq  # type: ignore[import-untyped]
from polars._typing import SchemaDict
from pydantic import ValidationError

from european_heritage_rag.domain.gold import (
    GoldChunk,
    GoldDatasetManifest,
    GoldFileRecord,
    GoldStatistics,
    GoldValidationIssue,
    GoldValidationReport,
    utc_now,
)
from european_heritage_rag.pipeline.bronze_store import sha256_hex
from european_heritage_rag.pipeline.chunking import GOLD_SCHEMA_VERSION
from european_heritage_rag.pipeline.gold import GoldTransformResult, gold_dataset_id
from european_heritage_rag.pipeline.silver_store import SilverFilesystemStore
from european_heritage_rag.pipeline.tokenization import TokenBoundary

_DISTRIBUTION_NAME = "european-heritage-rag"

_PAGE_SPAN_DTYPE = pl.List(
    pl.Struct(
        {
            "page_id": pl.String,
            "sequence_number": pl.Int64,
            "page_label": pl.String,
            "printed_page_number": pl.Int64,
            "canvas_id": pl.String,
            "image_url": pl.String,
            "chunk_char_start": pl.Int64,
            "chunk_char_end": pl.Int64,
            "source_char_start": pl.Int64,
            "source_char_end": pl.Int64,
        }
    )
)
GOLD_CHUNKS_SCHEMA_DEFINITION: SchemaDict = {
    "schema_version": pl.Int64,
    "gold_dataset_id": pl.String,
    "silver_dataset_id": pl.String,
    "chunk_id": pl.String,
    "profile_id": pl.String,
    "chunker_version": pl.String,
    "chunk_index": pl.Int64,
    "work_id": pl.String,
    "title": pl.String,
    "contributors": pl.List(pl.String),
    "production_dates": pl.List(pl.String),
    "production_labels": pl.List(pl.String),
    "subjects": pl.List(pl.String),
    "genres": pl.List(pl.String),
    "language_id": pl.String,
    "licence_id": pl.String,
    "licence_url": pl.String,
    "source_url": pl.String,
    "iiif_manifest_url": pl.String,
    "text": pl.String,
    "content_sha256": pl.String,
    "token_count": pl.Int64,
    "maximum_token_count": pl.Int64,
    "page_sequence_start": pl.Int64,
    "page_sequence_end": pl.Int64,
    "page_label_start": pl.String,
    "page_label_end": pl.String,
    "page_spans": _PAGE_SPAN_DTYPE,
    "overlap_previous_token_count": pl.Int64,
    "overlap_prefix_char_end": pl.Int64,
    "previous_chunk_id": pl.String,
    "next_chunk_id": pl.String,
    "inherited_quality_flags": pl.List(pl.String),
}
GOLD_CHUNKS_SCHEMA = pl.Schema(GOLD_CHUNKS_SCHEMA_DEFINITION)


class GoldContentConflictError(RuntimeError):
    """Raised when an existing complete dataset disagrees with its identity."""


@dataclass(frozen=True, slots=True)
class GoldBuildResult:
    """Published manifest and whether it was newly created."""

    manifest: GoldDatasetManifest
    created: bool


class GoldFilesystemStore:
    """Store complete deterministic Gold datasets on a local filesystem."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def dataset_directory(self, dataset_id: str) -> Path:
        """Return one dataset directory beneath the configured root."""

        return self.root / "wellcome" / f"dataset_id={dataset_id}"

    def manifest_path(self, dataset_id: str) -> Path:
        """Return the completeness marker for one dataset."""

        return self.dataset_directory(dataset_id) / "gold-manifest.json"

    def publish(
        self,
        result: GoldTransformResult,
        *,
        silver_store: SilverFilesystemStore,
        tokenizer: TokenBoundary,
        pipeline_version: str | None = None,
    ) -> GoldBuildResult:
        """Write, validate, and publish a complete Gold dataset."""

        existing = self.load_manifest(result.gold_dataset_id)
        if existing is not None:
            report = validate_gold_dataset(
                self,
                existing,
                silver_store=silver_store,
                tokenizer=tokenizer,
            )
            if not report.is_valid:
                raise GoldContentConflictError(
                    "existing Gold dataset is invalid: "
                    + ", ".join(issue.code for issue in report.issues)
                )
            if (
                existing.silver_manifest_sha256 != result.silver_manifest_sha256
                or existing.chunking_config != result.config
                or existing.scope != result.scope
                or existing.selected_work_ids != result.selected_work_ids
            ):
                raise GoldContentConflictError(
                    "existing Gold dataset has different inputs, configuration, "
                    "or scope"
                )
            return GoldBuildResult(manifest=existing, created=False)

        directory = self.dataset_directory(result.gold_dataset_id)
        directory.mkdir(parents=True, exist_ok=True)
        chunks_path = directory / "chunks.parquet"
        statistics_json_path = directory / "statistics.json"
        statistics_markdown_path = directory / "statistics.md"

        self._write_parquet_atomically(
            chunks_path,
            _frame_from_chunks(result.chunks),
        )
        self._write_bytes_atomically(
            statistics_json_path,
            f"{result.statistics.model_dump_json(indent=2)}\n".encode(),
        )
        self._write_bytes_atomically(
            statistics_markdown_path,
            _statistics_markdown(result.statistics).encode(),
        )
        files = tuple(
            _file_record(path)
            for path in (
                chunks_path,
                statistics_json_path,
                statistics_markdown_path,
            )
        )
        manifest = GoldDatasetManifest(
            gold_dataset_id=result.gold_dataset_id,
            silver_dataset_id=result.silver_dataset_id,
            silver_manifest_sha256=result.silver_manifest_sha256,
            gold_schema_version=GOLD_SCHEMA_VERSION,
            chunking_config=result.config,
            scope=result.scope,
            selected_work_ids=result.selected_work_ids,
            pipeline_version=pipeline_version or version(_DISTRIBUTION_NAME),
            generated_at=utc_now(),
            work_count=result.statistics.work_count,
            contributing_page_count=result.statistics.contributing_page_count,
            chunk_count=len(result.chunks),
            files=files,
        )
        self._write_bytes_atomically(
            self.manifest_path(result.gold_dataset_id),
            f"{manifest.model_dump_json(indent=2)}\n".encode(),
        )
        validation = validate_gold_dataset(
            self,
            manifest,
            silver_store=silver_store,
            tokenizer=tokenizer,
        )
        if not validation.is_valid:
            raise RuntimeError(
                "published Gold dataset failed validation: "
                + ", ".join(issue.code for issue in validation.issues)
            )
        return GoldBuildResult(manifest=manifest, created=True)

    def load_manifest(self, dataset_id: str) -> GoldDatasetManifest | None:
        """Load one manifest when its completeness marker exists."""

        path = self.manifest_path(dataset_id)
        if not path.is_file():
            return None
        manifest = GoldDatasetManifest.model_validate_json(path.read_bytes())
        if manifest.gold_dataset_id != dataset_id:
            raise ValueError("Gold manifest identity does not match its directory")
        return manifest

    def manifest_paths(self) -> tuple[Path, ...]:
        """Return complete Gold manifest paths in stable order."""

        pattern = "wellcome/dataset_id=*/gold-manifest.json"
        return tuple(sorted(path for path in self.root.glob(pattern) if path.is_file()))

    def list_manifests(self) -> tuple[GoldDatasetManifest, ...]:
        """Load complete Gold datasets newest first."""

        manifests = [
            GoldDatasetManifest.model_validate_json(path.read_bytes())
            for path in self.manifest_paths()
        ]
        return tuple(
            sorted(manifests, key=lambda item: item.generated_at, reverse=True)
        )

    def find_manifest(self, dataset_id: str) -> GoldDatasetManifest | None:
        """Find one complete dataset by deterministic ID."""

        return self.load_manifest(dataset_id)

    def read_chunks(self, dataset_id: str) -> tuple[GoldChunk, ...]:
        """Read and validate Gold chunks from Parquet."""

        path = self.dataset_directory(dataset_id) / "chunks.parquet"
        return tuple(
            GoldChunk.model_validate(row) for row in pl.read_parquet(path).to_dicts()
        )

    def read_statistics(self, dataset_id: str) -> GoldStatistics:
        """Read and validate measured chunk statistics."""

        path = self.dataset_directory(dataset_id) / "statistics.json"
        return GoldStatistics.model_validate_json(path.read_bytes())

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


def validate_gold_dataset(
    store: GoldFilesystemStore,
    manifest: GoldDatasetManifest,
    *,
    silver_store: SilverFilesystemStore | None = None,
    tokenizer: TokenBoundary | None = None,
) -> GoldValidationReport:
    """Validate files, rows, token limits, adjacency, and Silver provenance."""

    issues: list[GoldValidationIssue] = []
    directory = store.dataset_directory(manifest.gold_dataset_id)
    for record in manifest.files:
        path = directory / record.name
        if not path.is_file():
            issues.append(
                GoldValidationIssue(
                    code="missing_file",
                    message="Manifest-declared Gold file is missing",
                    filename=record.name,
                )
            )
            continue
        content = path.read_bytes()
        if len(content) != record.byte_length:
            issues.append(
                GoldValidationIssue(
                    code="byte_length_mismatch",
                    message="Gold file byte length differs from its receipt",
                    filename=record.name,
                )
            )
        if sha256_hex(content) != record.content_sha256:
            issues.append(
                GoldValidationIssue(
                    code="content_hash_mismatch",
                    message="Gold file SHA-256 differs from its receipt",
                    filename=record.name,
                )
            )
    for path in directory.glob("*.tmp"):
        issues.append(
            GoldValidationIssue(
                code="temporary_file",
                message="Incomplete Gold temporary file remains",
                filename=path.name,
            )
        )

    chunks: tuple[GoldChunk, ...] = ()
    chunks_loaded = False
    try:
        _validate_parquet_schema(directory / "chunks.parquet")
        chunks = store.read_chunks(manifest.gold_dataset_id)
        chunks_loaded = True
    except (OSError, ValueError, ValidationError, pl.exceptions.PolarsError) as error:
        issues.append(
            GoldValidationIssue(
                code="invalid_chunks_parquet",
                message=str(error),
                filename="chunks.parquet",
            )
        )
    if chunks_loaded:
        ids = tuple(chunk.chunk_id for chunk in chunks)
        if len(set(ids)) != len(ids):
            issues.append(
                GoldValidationIssue(
                    code="duplicate_chunk_id",
                    message="Chunk IDs must be unique",
                    filename="chunks.parquet",
                )
            )
        if len(chunks) != manifest.chunk_count:
            issues.append(
                GoldValidationIssue(
                    code="chunk_count_mismatch",
                    message="Manifest chunk count does not match Parquet",
                    filename="chunks.parquet",
                )
            )
        _validate_chunk_rows(chunks, manifest, issues, tokenizer)

    try:
        statistics = store.read_statistics(manifest.gold_dataset_id)
        if (
            statistics.gold_dataset_id != manifest.gold_dataset_id
            or statistics.chunk_count != manifest.chunk_count
            or statistics.work_count != manifest.work_count
            or statistics.contributing_page_count != manifest.contributing_page_count
        ):
            issues.append(
                GoldValidationIssue(
                    code="statistics_count_mismatch",
                    message="Statistics do not match manifest counts",
                    filename="statistics.json",
                )
            )
    except (OSError, ValidationError) as error:
        issues.append(
            GoldValidationIssue(
                code="invalid_statistics",
                message=str(error),
                filename="statistics.json",
            )
        )

    if silver_store is not None and chunks_loaded:
        _validate_silver_provenance(
            chunks,
            manifest,
            silver_store,
            issues,
        )
    return GoldValidationReport(
        gold_dataset_id=manifest.gold_dataset_id,
        issues=tuple(issues),
    )


def _validate_chunk_rows(
    chunks: tuple[GoldChunk, ...],
    manifest: GoldDatasetManifest,
    issues: list[GoldValidationIssue],
    tokenizer: TokenBoundary | None,
) -> None:
    """Validate manifest consistency, token counts, and adjacency."""

    by_work: dict[str, list[GoldChunk]] = {}
    for chunk in chunks:
        by_work.setdefault(chunk.work_id, []).append(chunk)
        if (
            chunk.gold_dataset_id != manifest.gold_dataset_id
            or chunk.silver_dataset_id != manifest.silver_dataset_id
            or chunk.profile_id != manifest.chunking_config.profile_id
            or chunk.chunker_version != manifest.chunking_config.chunker_version
        ):
            issues.append(
                GoldValidationIssue(
                    code="chunk_manifest_mismatch",
                    message=f"Chunk {chunk.chunk_id} disagrees with the manifest",
                    filename="chunks.parquet",
                )
            )
        if tokenizer is not None:
            recounted = tokenizer.token_count(chunk.text)
            if recounted != chunk.token_count:
                issues.append(
                    GoldValidationIssue(
                        code="token_count_mismatch",
                        message=(
                            f"Chunk {chunk.chunk_id} stores {chunk.token_count} "
                            f"tokens but tokenizer returns {recounted}"
                        ),
                        filename="chunks.parquet",
                    )
                )
    page_ids = {span.page_id for chunk in chunks for span in chunk.page_spans}
    if len(by_work) != manifest.work_count:
        issues.append(
            GoldValidationIssue(
                code="work_count_mismatch",
                message="Manifest work count does not match Gold chunks",
                filename="chunks.parquet",
            )
        )
    if len(page_ids) != manifest.contributing_page_count:
        issues.append(
            GoldValidationIssue(
                code="contributing_page_count_mismatch",
                message="Manifest page count does not match Gold page spans",
                filename="chunks.parquet",
            )
        )
    for work_id, work_chunks in by_work.items():
        ordered = sorted(work_chunks, key=lambda item: item.chunk_index)
        if [chunk.chunk_index for chunk in ordered] != list(range(len(ordered))):
            issues.append(
                GoldValidationIssue(
                    code="chunk_index_gap",
                    message=f"Work {work_id} chunk indexes are not contiguous",
                    filename="chunks.parquet",
                )
            )
        for index, chunk in enumerate(ordered):
            expected_previous = ordered[index - 1].chunk_id if index else None
            expected_next = (
                ordered[index + 1].chunk_id if index + 1 < len(ordered) else None
            )
            if (
                chunk.previous_chunk_id != expected_previous
                or chunk.next_chunk_id != expected_next
            ):
                issues.append(
                    GoldValidationIssue(
                        code="invalid_adjacency",
                        message=f"Chunk {chunk.chunk_id} has invalid adjacency links",
                        filename="chunks.parquet",
                    )
                )


def _validate_silver_provenance(
    chunks: tuple[GoldChunk, ...],
    manifest: GoldDatasetManifest,
    silver_store: SilverFilesystemStore,
    issues: list[GoldValidationIssue],
) -> None:
    """Require every eligible Silver page and every Gold reference to reconcile."""

    silver_manifest = silver_store.find_manifest(manifest.silver_dataset_id)
    if silver_manifest is None:
        issues.append(
            GoldValidationIssue(
                code="missing_silver_dataset",
                message="Parent Silver dataset is unavailable",
            )
        )
        return
    silver_manifest_content = silver_store.manifest_path(
        manifest.silver_dataset_id
    ).read_bytes()
    actual_silver_manifest_sha256 = sha256_hex(silver_manifest_content)
    if actual_silver_manifest_sha256 != manifest.silver_manifest_sha256:
        issues.append(
            GoldValidationIssue(
                code="silver_manifest_hash_mismatch",
                message="Parent Silver manifest SHA-256 differs from Gold lineage",
            )
        )
    expected_gold_dataset_id = gold_dataset_id(
        silver_manifest,
        manifest.silver_manifest_sha256,
        manifest.chunking_config,
        selected_work_ids=manifest.selected_work_ids,
    )
    if expected_gold_dataset_id != manifest.gold_dataset_id:
        issues.append(
            GoldValidationIssue(
                code="dataset_identity_mismatch",
                message="Gold dataset ID does not match parent, config, and scope",
            )
        )
    works = silver_store.read_works(manifest.silver_dataset_id)
    pages = silver_store.read_pages(manifest.silver_dataset_id)
    selected = set(manifest.selected_work_ids)
    unknown_selected = sorted(selected - {work.work_id for work in works})
    if unknown_selected:
        issues.append(
            GoldValidationIssue(
                code="unknown_selected_work",
                message=(
                    f"Selected Gold scope references unknown works: {unknown_selected}"
                ),
            )
        )
    eligible_work_ids = {
        work.work_id
        for work in works
        if (not selected or work.work_id in selected)
        and work.language_ids == (manifest.chunking_config.eligible_language_id,)
        and work.licence_id is not None
        and work.licence_url is not None
    }
    eligible_pages = {
        page.page_id: page
        for page in pages
        if page.work_id in eligible_work_ids and page.clean_text.strip()
    }
    contributing = {
        span.page_id: (chunk.work_id, span.sequence_number)
        for chunk in chunks
        for span in chunk.page_spans
    }
    unknown = sorted(set(contributing) - set(eligible_pages))
    missing = sorted(set(eligible_pages) - set(contributing))
    if unknown:
        issues.append(
            GoldValidationIssue(
                code="unknown_page_reference",
                message=f"Chunks reference ineligible or unknown pages: {unknown}",
                filename="chunks.parquet",
            )
        )
    if missing:
        issues.append(
            GoldValidationIssue(
                code="missing_page_coverage",
                message=f"Eligible Silver pages are absent from chunks: {missing}",
                filename="chunks.parquet",
            )
        )
    for page_id, (work_id, sequence_number) in contributing.items():
        page = eligible_pages.get(page_id)
        if page is not None and (
            page.work_id != work_id or page.sequence_number != sequence_number
        ):
            issues.append(
                GoldValidationIssue(
                    code="page_provenance_mismatch",
                    message=f"Page {page_id} has mismatched work or sequence",
                    filename="chunks.parquet",
                )
            )


def _frame_from_chunks(chunks: tuple[GoldChunk, ...]) -> pl.DataFrame:
    rows = [chunk.model_dump(mode="json") for chunk in chunks]
    return pl.DataFrame(rows, schema=GOLD_CHUNKS_SCHEMA, strict=True)


def _validate_parquet_schema(path: Path) -> None:
    polars_schema = pl.read_parquet_schema(path)
    if polars_schema != GOLD_CHUNKS_SCHEMA:
        raise ValueError(
            f"unexpected Polars schema: {polars_schema}; expected {GOLD_CHUNKS_SCHEMA}"
        )
    arrow_schema = pq.read_schema(path)
    if arrow_schema.names != list(GOLD_CHUNKS_SCHEMA):
        raise ValueError(f"unexpected PyArrow fields: {arrow_schema.names}")


def _file_record(path: Path) -> GoldFileRecord:
    content = path.read_bytes()
    return GoldFileRecord(
        name=path.name,
        byte_length=len(content),
        content_sha256=sha256_hex(content),
    )


def _temporary_path(destination: Path) -> Path:
    return destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")


def _sync_file(path: Path) -> None:
    with path.open("r+b") as stream:
        os.fsync(stream.fileno())


def _statistics_markdown(statistics: GoldStatistics) -> str:
    exclusions = (
        "\n".join(
            f"- `{item.kind}:{item.identifier}`: {item.reason}"
            for item in statistics.exclusions
        )
        or "- None"
    )
    return (
        "# Gold chunk statistics\n\n"
        f"- Gold dataset ID: `{statistics.gold_dataset_id}`\n"
        f"- Silver dataset ID: `{statistics.silver_dataset_id}`\n"
        f"- Profile: `{statistics.profile_id}`\n"
        f"- Works: {statistics.work_count}\n"
        f"- Contributing pages: {statistics.contributing_page_count}\n"
        f"- Chunks: {statistics.chunk_count}\n"
        f"- Empty chunks: {statistics.empty_chunk_count}\n"
        f"- Short chunks: {statistics.short_chunk_count}\n"
        f"- Tokens min/mean/median/p95/max: {statistics.minimum_tokens}/"
        f"{statistics.mean_tokens:.1f}/{statistics.median_tokens:.1f}/"
        f"{statistics.p95_tokens:.1f}/{statistics.maximum_tokens}\n"
        f"- Mean/max pages per chunk: {statistics.mean_pages_per_chunk:.2f}/"
        f"{statistics.maximum_pages_per_chunk}\n"
        f"- Requested overlap: {statistics.requested_overlap_tokens}\n"
        f"- Actual repeated tokens: {statistics.actual_overlap_tokens}\n"
        f"- Overlap ratio: {statistics.overlap_ratio:.4f}\n"
        f"- Output token inflation: "
        f"{statistics.output_token_inflation_ratio:.4f}\n\n"
        "These statistics describe chunk construction. They do not establish "
        "retrieval quality or select a winning profile.\n\n"
        "## Exclusions\n\n"
        f"{exclusions}\n"
    )
