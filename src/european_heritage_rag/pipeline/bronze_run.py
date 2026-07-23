"""Lifecycle coordination for one resumable Bronze ingestion run."""

from datetime import datetime

from pydantic import AnyHttpUrl

from european_heritage_rag.pipeline.bronze import (
    BronzeFailureRecord,
    BronzeResourceIdentity,
    BronzeResourceRecord,
    BronzeResourceType,
    BronzeRunIdentity,
    BronzeRunManifest,
    BronzeRunStatus,
    WellcomeBronzeParameters,
)
from european_heritage_rag.pipeline.bronze_store import (
    BronzeFilesystemStore,
    BronzeWriteResult,
)


class BronzeRunRecorder:
    """Keep raw writes and the run ledger consistent after every event."""

    def __init__(
        self,
        store: BronzeFilesystemStore,
        manifest: BronzeRunManifest,
    ) -> None:
        self._store = store
        self._manifest = manifest

    @classmethod
    def start(
        cls,
        store: BronzeFilesystemStore,
        *,
        identity: BronzeRunIdentity,
        parameters: WellcomeBronzeParameters,
        catalogue_base_url: AnyHttpUrl,
        pipeline_version: str,
        started_at: datetime,
        now: datetime,
        resume: bool,
    ) -> "BronzeRunRecorder":
        """Create a new ledger or reopen the matching existing ledger."""

        existing = store.load_manifest(identity)
        if resume:
            if existing is None:
                raise ValueError("no Bronze run manifest exists to resume")
            if existing.parameters != parameters:
                raise ValueError(
                    "Bronze resume parameters do not match the existing run"
                )
            values = existing.model_dump()
            values.update(
                {
                    "status": BronzeRunStatus.RUNNING,
                    "updated_at": now,
                    "finished_at": None,
                }
            )
            manifest = BronzeRunManifest.model_validate(values)
        else:
            if existing is not None:
                raise ValueError(f"Bronze run already exists: {identity.run_id}")
            manifest = BronzeRunManifest(
                identity=identity,
                status=BronzeRunStatus.RUNNING,
                pipeline_version=pipeline_version,
                parameters=parameters,
                catalogue_base_url=catalogue_base_url,
                started_at=started_at,
                updated_at=now,
                requested_work_count=parameters.limit,
                discovered_work_count=0,
                completed_work_count=0,
            )

        store.write_manifest(manifest)
        return cls(store, manifest)

    @property
    def manifest(self) -> BronzeRunManifest:
        """Return the latest validated in-memory ledger."""

        return self._manifest

    def record_resource(
        self,
        *,
        resource: BronzeResourceIdentity,
        content: bytes,
        acquired_at: datetime,
        content_type: str | None,
        now: datetime,
    ) -> BronzeWriteResult:
        """Write one immutable payload and commit its receipt to the ledger."""

        result = self._store.write_resource(
            run=self._manifest.identity,
            resource=resource,
            content=content,
            acquired_at=acquired_at,
            content_type=content_type,
        )
        resources_by_id = {
            record.resource_id: record for record in self._manifest.resources
        }
        existing = resources_by_id.get(result.record.resource_id)
        if existing is not None:
            if existing.content_sha256 != result.record.content_sha256:
                raise RuntimeError(
                    "existing manifest receipt conflicts with stored content"
                )
        else:
            resources_by_id[result.record.resource_id] = result.record

        resources = tuple(
            sorted(
                resources_by_id.values(),
                key=lambda record: record.relative_path,
            )
        )
        annotation_count = sum(
            record.resource_type is BronzeResourceType.OCR_ANNOTATION_LIST
            for record in resources
        )
        self._update(
            now=now,
            resources=resources,
            annotation_count=annotation_count,
        )
        return result

    def record_discovery(self, count: int, *, now: datetime) -> None:
        """Record the bounded number of eligible works selected by discovery."""

        self._update(now=now, discovered_work_count=count)

    def record_work_success(
        self,
        work_id: str,
        *,
        canvas_count: int,
        missing_ocr_page_count: int,
        now: datetime,
    ) -> None:
        """Commit one complete work and resolve its earlier failures."""

        completed = set(self._manifest.completed_work_ids)
        if work_id in completed:
            return
        completed.add(work_id)
        failures = tuple(
            _resolve_failure(failure, now)
            if failure.work_id == work_id and failure.resolved_at is None
            else failure
            for failure in self._manifest.failures
        )
        self._update(
            now=now,
            completed_work_ids=tuple(sorted(completed)),
            completed_work_count=len(completed),
            canvas_count=self._manifest.canvas_count + canvas_count,
            missing_ocr_page_count=(
                self._manifest.missing_ocr_page_count + missing_ocr_page_count
            ),
            failures=failures,
        )

    def record_failure(
        self,
        *,
        work_id: str | None,
        resource_type: BronzeResourceType | None,
        source_url: AnyHttpUrl,
        error: Exception,
        now: datetime,
    ) -> None:
        """Append a structured failed URL without discarding earlier history."""

        message = str(error).strip() or type(error).__name__
        failure = BronzeFailureRecord(
            occurred_at=now,
            work_id=work_id,
            resource_type=resource_type,
            source_url=source_url,
            error_type=type(error).__name__,
            message=message,
        )
        self._update(
            now=now,
            failures=(*self._manifest.failures, failure),
        )

    def finish(
        self,
        status: BronzeRunStatus,
        *,
        now: datetime,
    ) -> BronzeRunManifest:
        """Write the terminal ledger and return it."""

        if status is BronzeRunStatus.RUNNING:
            raise ValueError("finish requires a terminal Bronze status")
        self._update(status=status, now=now, finished_at=now)
        return self._manifest

    def _update(self, *, now: datetime, **changes: object) -> None:
        values = self._manifest.model_dump()
        values.update(changes)
        values["updated_at"] = now
        self._manifest = BronzeRunManifest.model_validate(values)
        self._store.write_manifest(self._manifest)


def _resolve_failure(
    failure: BronzeFailureRecord,
    resolved_at: datetime,
) -> BronzeFailureRecord:
    values = failure.model_dump()
    values["resolved_at"] = resolved_at
    return BronzeFailureRecord.model_validate(values)


def resource_records_for_work(
    manifest: BronzeRunManifest,
    work_id: str,
) -> tuple[BronzeResourceRecord, ...]:
    """Return one work's inventory in portable path order."""

    return tuple(record for record in manifest.resources if record.work_id == work_id)
