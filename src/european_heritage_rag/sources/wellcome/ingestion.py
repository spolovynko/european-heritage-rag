"""Sequential Wellcome ingestion orchestration and resumable run state."""

import hashlib
import json
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Literal, Protocol
from uuid import uuid4

import httpx2
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field

from european_heritage_rag.core.config import AppSettings
from european_heritage_rag.pipeline.bronze import (
    BronzeResourceIdentity,
    BronzeResourceType,
    BronzeRunIdentity,
    BronzeRunStatus,
    WellcomeBronzeParameters,
)
from european_heritage_rag.pipeline.bronze_run import BronzeRunRecorder
from european_heritage_rag.pipeline.bronze_store import BronzeFilesystemStore
from european_heritage_rag.sources.wellcome.client import (
    RawResourceObserver,
    WellcomeClient,
    manifest_url_for,
)
from european_heritage_rag.sources.wellcome.models import (
    CatalogueWork,
    RawWellcomeResource,
    TraversedWork,
)

_DISTRIBUTION_NAME = "european-heritage-rag"
_DEFAULT_CATALOGUE_BASE_URL = AnyHttpUrl(
    "https://api.wellcomecollection.org/catalogue/v2/"
)

RunStatus = Literal[
    "idle",
    "running",
    "completed",
    "completed_with_failures",
    "failed",
]
EventLevel = Literal["info", "warning", "error"]


class IngestionEvent(BaseModel):
    """One recent operator-facing ingestion event."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    timestamp: datetime
    level: EventLevel
    message: str = Field(min_length=1)
    work_id: str | None = None


class IngestionStatus(BaseModel):
    """Serializable current status shared by the CLI, API, and UI."""

    model_config = ConfigDict(extra="forbid")

    status: RunStatus = "idle"
    run_id: str | None = None
    requested_limit: int = Field(default=0, ge=0, le=100)
    query: str | None = None
    language: str = "eng"
    dry_run: bool = False
    resumed: bool = False
    current_work_id: str | None = None
    current_work_title: str | None = None
    works_discovered: int = Field(default=0, ge=0)
    works_completed: int = Field(default=0, ge=0)
    pages_downloaded: int = Field(default=0, ge=0)
    missing_ocr_pages: int = Field(default=0, ge=0)
    retry_count: int = Field(default=0, ge=0)
    failure_count: int = Field(default=0, ge=0)
    failures: dict[str, str] = Field(default_factory=dict)
    recent_events: list[IngestionEvent] = Field(default_factory=list)
    started_at: datetime | None = None
    updated_at: datetime | None = None
    finished_at: datetime | None = None


class IngestionCheckpoint(BaseModel):
    """Minimal durable state needed to resume without storing source payloads."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    fingerprint: str = Field(min_length=64, max_length=64)
    run_id: str = Field(min_length=1)
    started_at: datetime
    completed_work_ids: tuple[str, ...] = ()
    pages_downloaded: int = Field(default=0, ge=0)
    missing_ocr_pages: int = Field(default=0, ge=0)
    retry_count: int = Field(default=0, ge=0)
    failures: dict[str, str] = Field(default_factory=dict)


class IngestionClient(Protocol):
    """Client behavior required by the orchestration layer."""

    @property
    def retry_count(self) -> int:
        """Return retries performed by this client."""

    def discover_works(
        self,
        *,
        limit: int,
        query: str | None = None,
        language: str = "eng",
        raw_resource_observer: RawResourceObserver | None = None,
    ) -> tuple[CatalogueWork, ...]:
        """Discover eligible works."""

    def traverse_work(self, work: CatalogueWork) -> TraversedWork:
        """Traverse one discovered work."""

    def traverse_work_with_resources(
        self,
        work: CatalogueWork,
        *,
        raw_resource_observer: RawResourceObserver | None = None,
    ) -> TraversedWork:
        """Traverse one work while exposing raw payloads before validation."""


class IngestionStateStore:
    """Persist the current status and minimal checkpoint as JSON files."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.status_path = directory / "wellcome-status.json"
        self.checkpoint_path = directory / "wellcome-checkpoint.json"

    def load_status(self) -> IngestionStatus:
        """Load the current status or return an idle status before the first run."""

        if not self.status_path.is_file():
            return IngestionStatus()

        return IngestionStatus.model_validate_json(
            self.status_path.read_text(encoding="utf-8")
        )

    def save_status(self, status: IngestionStatus) -> None:
        """Atomically replace the operator-facing status file."""

        self._write_model(self.status_path, status)

    def load_checkpoint(self) -> IngestionCheckpoint | None:
        """Load the resume checkpoint when one exists."""

        if not self.checkpoint_path.is_file():
            return None

        return IngestionCheckpoint.model_validate_json(
            self.checkpoint_path.read_text(encoding="utf-8")
        )

    def save_checkpoint(self, checkpoint: IngestionCheckpoint) -> None:
        """Atomically replace the resume checkpoint."""

        self._write_model(self.checkpoint_path, checkpoint)

    def _write_model(self, path: Path, model: BaseModel) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        temporary_path = path.with_name(f".{path.name}.tmp")
        temporary_path.write_text(
            f"{model.model_dump_json(indent=2)}\n",
            encoding="utf-8",
        )
        temporary_path.replace(path)


def ingestion_fingerprint(
    *,
    limit: int,
    query: str | None,
    language: str,
) -> str:
    """Create a stable fingerprint for options that define a resumable run."""

    normalized_query = query.strip() if query and query.strip() else None
    payload = json.dumps(
        {
            "language": language,
            "limit": limit,
            "query": normalized_query,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class WellcomeIngestionRunner:
    """Run discovery and traversal sequentially with durable progress."""

    def __init__(
        self,
        client: IngestionClient,
        state_store: IngestionStateStore,
        bronze_store: BronzeFilesystemStore | None = None,
        *,
        pipeline_version: str = "0.1.0",
        catalogue_base_url: AnyHttpUrl = _DEFAULT_CATALOGUE_BASE_URL,
    ) -> None:
        self._client = client
        self._state_store = state_store
        self._bronze_store = bronze_store
        self._pipeline_version = pipeline_version
        self._catalogue_base_url = catalogue_base_url

    def run(
        self,
        *,
        limit: int,
        query: str | None = None,
        language: str = "eng",
        resume: bool = False,
        dry_run: bool = False,
    ) -> IngestionStatus:
        """Discover and traverse works, checkpointing after every work."""

        if resume and dry_run:
            raise ValueError("resume and dry-run cannot be used together")
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        if language != "eng":
            raise ValueError("only English ingestion is supported")

        normalized_query = query.strip() if query and query.strip() else None
        fingerprint = ingestion_fingerprint(
            limit=limit,
            query=normalized_query,
            language=language,
        )
        checkpoint = self._initial_checkpoint(
            fingerprint=fingerprint,
            resume=resume,
        )
        completed_work_ids = set(checkpoint.completed_work_ids)
        failures = dict(checkpoint.failures)
        bronze_recorder: BronzeRunRecorder | None = None

        if not dry_run and self._bronze_store is not None:
            now = datetime.now(UTC)
            bronze_recorder = BronzeRunRecorder.start(
                self._bronze_store,
                identity=BronzeRunIdentity(
                    ingestion_date=checkpoint.started_at.astimezone(UTC).date(),
                    run_id=checkpoint.run_id,
                ),
                parameters=WellcomeBronzeParameters(
                    limit=limit,
                    query=normalized_query,
                    language="eng",
                ),
                catalogue_base_url=self._catalogue_base_url,
                pipeline_version=self._pipeline_version,
                started_at=checkpoint.started_at,
                now=now,
                resume=resume,
            )
            if resume:
                completed_work_ids = set(bronze_recorder.manifest.completed_work_ids)
                failures = _active_bronze_failures(bronze_recorder)

        status = IngestionStatus(
            status="running",
            run_id=checkpoint.run_id,
            requested_limit=limit,
            query=normalized_query,
            language=language,
            dry_run=dry_run,
            resumed=resume,
            works_completed=len(completed_work_ids),
            pages_downloaded=(
                bronze_recorder.manifest.canvas_count
                if bronze_recorder is not None
                else checkpoint.pages_downloaded
            ),
            missing_ocr_pages=(
                bronze_recorder.manifest.missing_ocr_page_count
                if bronze_recorder is not None
                else checkpoint.missing_ocr_pages
            ),
            retry_count=checkpoint.retry_count,
            failure_count=len(failures),
            failures=failures,
            started_at=checkpoint.started_at,
        )
        self._record_event(
            status,
            level="info",
            message="Resumed ingestion run" if resume else "Started ingestion run",
        )

        if not dry_run:
            self._state_store.save_checkpoint(checkpoint)

        try:
            if bronze_recorder is None:
                works = self._client.discover_works(
                    limit=limit,
                    query=normalized_query,
                    language=language,
                )
            else:
                works = self._client.discover_works(
                    limit=limit,
                    query=normalized_query,
                    language=language,
                    raw_resource_observer=_bronze_observer(bronze_recorder),
                )
        except Exception as error:
            status.status = "failed"
            status.finished_at = datetime.now(UTC)
            status.failures["discovery"] = _error_message(error)
            status.failure_count = len(status.failures)
            self._record_event(
                status,
                level="error",
                message=f"Discovery failed: {_error_message(error)}",
            )
            if bronze_recorder is not None:
                now = datetime.now(UTC)
                bronze_recorder.record_failure(
                    work_id=None,
                    resource_type=None,
                    source_url=_error_source_url(
                        error,
                        fallback=self._catalogue_base_url,
                    ),
                    error=error,
                    now=now,
                )
                bronze_recorder.finish(BronzeRunStatus.FAILED, now=now)
            raise

        status.works_discovered = len(works)
        if bronze_recorder is not None:
            bronze_recorder.record_discovery(
                len(works),
                now=datetime.now(UTC),
            )
        status.retry_count = checkpoint.retry_count + self._client.retry_count
        self._record_event(
            status,
            level="info",
            message=f"Discovered {len(works)} eligible work(s)",
        )

        if dry_run:
            status.status = "completed"
            status.finished_at = datetime.now(UTC)
            self._record_event(
                status,
                level="info",
                message="Dry run completed without manifest or OCR requests",
            )
            return status

        for work in works:
            if work.id in completed_work_ids:
                self._record_event(
                    status,
                    level="info",
                    message="Skipped work already recorded in checkpoint",
                    work_id=work.id,
                )
                continue

            status.current_work_id = work.id
            status.current_work_title = work.title
            self._record_event(
                status,
                level="info",
                message=f"Traversing {work.title}",
                work_id=work.id,
            )

            try:
                if bronze_recorder is None:
                    traversed = self._client.traverse_work(work)
                else:
                    traversed = self._client.traverse_work_with_resources(
                        work,
                        raw_resource_observer=_bronze_observer(bronze_recorder),
                    )
            except Exception as error:
                failures[work.id] = _error_message(error)
                if bronze_recorder is not None:
                    fallback_url = manifest_url_for(work)
                    bronze_recorder.record_failure(
                        work_id=work.id,
                        resource_type=_failed_resource_type(
                            error,
                            fallback_manifest_url=fallback_url,
                        ),
                        source_url=_error_source_url(
                            error,
                            fallback=AnyHttpUrl(
                                fallback_url or str(self._catalogue_base_url)
                            ),
                        ),
                        error=error,
                        now=datetime.now(UTC),
                    )
                status.failures = dict(failures)
                status.failure_count = len(failures)
                status.retry_count = checkpoint.retry_count + self._client.retry_count
                self._record_event(
                    status,
                    level="error",
                    message=f"Work failed: {_error_message(error)}",
                    work_id=work.id,
                )
            else:
                completed_work_ids.add(work.id)
                failures.pop(work.id, None)
                status.pages_downloaded += len(traversed.pages)
                missing_pages = sum(page.text is None for page in traversed.pages)
                status.missing_ocr_pages += missing_pages
                if bronze_recorder is not None:
                    bronze_recorder.record_work_success(
                        work.id,
                        canvas_count=len(traversed.pages),
                        missing_ocr_page_count=missing_pages,
                        now=datetime.now(UTC),
                    )
                status.works_completed = len(completed_work_ids)
                status.retry_count = checkpoint.retry_count + self._client.retry_count
                status.failures = dict(failures)
                status.failure_count = len(failures)
                self._record_event(
                    status,
                    level="warning" if missing_pages else "info",
                    message=(
                        f"Completed {len(traversed.pages)} page(s); "
                        f"{missing_pages} without OCR"
                    ),
                    work_id=work.id,
                )

            status.works_completed = len(completed_work_ids)
            status.retry_count = checkpoint.retry_count + self._client.retry_count
            status.failures = dict(failures)
            status.failure_count = len(failures)
            self._state_store.save_checkpoint(
                self._checkpoint_from_status(
                    fingerprint=fingerprint,
                    status=status,
                    completed_work_ids=completed_work_ids,
                )
            )

        status.current_work_id = None
        status.current_work_title = None
        status.status = "completed_with_failures" if failures else "completed"
        status.finished_at = datetime.now(UTC)
        if bronze_recorder is not None:
            bronze_recorder.finish(
                (
                    BronzeRunStatus.COMPLETED_WITH_FAILURES
                    if failures
                    else BronzeRunStatus.COMPLETED
                ),
                now=status.finished_at,
            )
        self._record_event(
            status,
            level="warning" if failures else "info",
            message=(
                "Ingestion completed with failures"
                if failures
                else "Ingestion completed successfully"
            ),
        )
        return status

    def _initial_checkpoint(
        self,
        *,
        fingerprint: str,
        resume: bool,
    ) -> IngestionCheckpoint:
        if resume:
            checkpoint = self._state_store.load_checkpoint()
            if checkpoint is None:
                raise ValueError("no Wellcome checkpoint exists to resume")
            if checkpoint.fingerprint != fingerprint:
                raise ValueError(
                    "resume options do not match the existing Wellcome checkpoint"
                )
            return checkpoint

        return IngestionCheckpoint(
            fingerprint=fingerprint,
            run_id=uuid4().hex,
            started_at=datetime.now(UTC),
        )

    def _checkpoint_from_status(
        self,
        *,
        fingerprint: str,
        status: IngestionStatus,
        completed_work_ids: set[str],
    ) -> IngestionCheckpoint:
        if status.run_id is None or status.started_at is None:
            raise RuntimeError("running ingestion status is missing run identity")

        return IngestionCheckpoint(
            fingerprint=fingerprint,
            run_id=status.run_id,
            started_at=status.started_at,
            completed_work_ids=tuple(sorted(completed_work_ids)),
            pages_downloaded=status.pages_downloaded,
            missing_ocr_pages=status.missing_ocr_pages,
            retry_count=status.retry_count,
            failures=dict(status.failures),
        )

    def _record_event(
        self,
        status: IngestionStatus,
        *,
        level: EventLevel,
        message: str,
        work_id: str | None = None,
    ) -> None:
        now = datetime.now(UTC)
        status.updated_at = now
        status.recent_events.append(
            IngestionEvent(
                timestamp=now,
                level=level,
                message=message,
                work_id=work_id,
            )
        )
        status.recent_events = status.recent_events[-20:]
        self._state_store.save_status(status)


def run_wellcome_ingestion(
    settings: AppSettings,
    *,
    limit: int,
    query: str | None = None,
    language: str = "eng",
    resume: bool = False,
    dry_run: bool = False,
) -> IngestionStatus:
    """Construct production dependencies and run Wellcome ingestion."""

    state_store = IngestionStateStore(settings.ingestion_state_directory)
    bronze_store = BronzeFilesystemStore(settings.bronze_data_directory)
    with WellcomeClient(settings) as client:
        runner = WellcomeIngestionRunner(
            client,
            state_store,
            bronze_store,
            pipeline_version=version(_DISTRIBUTION_NAME),
            catalogue_base_url=settings.wellcome_catalogue_base_url,
        )
        return runner.run(
            limit=limit,
            query=query,
            language=language,
            resume=resume,
            dry_run=dry_run,
        )


def _error_message(error: Exception) -> str:
    message = str(error).strip()
    return f"{type(error).__name__}: {message}" if message else type(error).__name__


def _bronze_observer(
    recorder: BronzeRunRecorder,
) -> RawResourceObserver:
    def record(raw: RawWellcomeResource) -> None:
        recorder.record_resource(
            resource=BronzeResourceIdentity(
                resource_type=BronzeResourceType(raw.resource_type),
                work_id=raw.work_id,
                source_url=raw.source_url,
                canvas_index=raw.canvas_index,
                annotation_index=raw.annotation_index,
            ),
            content=raw.content,
            acquired_at=raw.acquired_at,
            content_type=raw.content_type,
            now=datetime.now(UTC),
        )

    return record


def _error_source_url(
    error: Exception,
    *,
    fallback: AnyHttpUrl,
) -> AnyHttpUrl:
    if isinstance(error, httpx2.HTTPError):
        return AnyHttpUrl(str(error.request.url))
    return fallback


def _failed_resource_type(
    error: Exception,
    *,
    fallback_manifest_url: str | None,
) -> BronzeResourceType | None:
    if not isinstance(error, httpx2.HTTPError):
        return (
            BronzeResourceType.IIIF_MANIFEST
            if fallback_manifest_url is not None
            else None
        )
    failed_url = str(error.request.url)
    if fallback_manifest_url is not None and failed_url == fallback_manifest_url:
        return BronzeResourceType.IIIF_MANIFEST
    return BronzeResourceType.OCR_ANNOTATION_LIST


def _active_bronze_failures(
    recorder: BronzeRunRecorder,
) -> dict[str, str]:
    failures: dict[str, str] = {}
    for failure in recorder.manifest.failures:
        if failure.resolved_at is not None:
            continue
        key = failure.work_id or "discovery"
        failures[key] = f"{failure.error_type}: {failure.message}"
    return failures
