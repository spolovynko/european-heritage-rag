"""Identity and path contracts for the Bronze data layer."""

from datetime import UTC, date
from enum import StrEnum
from hashlib import sha256
from pathlib import PurePosixPath
from typing import Literal, Self

from pydantic import (
    AnyHttpUrl,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

_SAFE_IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]*$"


class BronzeModel(BaseModel):
    """Base model for strict immutable Bronze contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class BronzeRunStatus(StrEnum):
    """Lifecycle states recorded by a Bronze run."""

    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_FAILURES = "completed_with_failures"
    FAILED = "failed"


class BronzeResourceType(StrEnum):
    """Raw Wellcome resource types stored in Bronze."""

    CATALOGUE_WORK = "catalogue_work"
    IIIF_MANIFEST = "iiif_manifest"
    OCR_ANNOTATION_LIST = "ocr_annotation_list"


class BronzeRunIdentity(BronzeModel):
    """Stable identity and directory partition for one ingestion run."""

    source: Literal["wellcome"] = "wellcome"
    ingestion_date: date
    run_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=_SAFE_IDENTIFIER_PATTERN,
    )

    @property
    def relative_directory(self) -> PurePosixPath:
        """Return the portable directory used beneath the Bronze root."""

        return (
            PurePosixPath(self.source)
            / f"ingestion_date={self.ingestion_date.isoformat()}"
            / f"run_id={self.run_id}"
        )


class BronzeResourceIdentity(BronzeModel):
    """Stable identity and relative path for one raw source resource."""

    resource_type: BronzeResourceType
    work_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=_SAFE_IDENTIFIER_PATTERN,
    )
    source_url: AnyHttpUrl
    canvas_index: int | None = Field(default=None, ge=0)
    annotation_index: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_annotation_position(self) -> Self:
        """Require canvas coordinates only for OCR annotation resources."""

        is_annotation = self.resource_type is BronzeResourceType.OCR_ANNOTATION_LIST
        has_complete_position = (
            self.canvas_index is not None and self.annotation_index is not None
        )
        has_any_position = (
            self.canvas_index is not None or self.annotation_index is not None
        )

        if is_annotation and not has_complete_position:
            raise ValueError(
                "OCR annotation resources require canvas_index and annotation_index"
            )

        if not is_annotation and has_any_position:
            raise ValueError(
                "canvas_index and annotation_index are only valid for "
                "OCR annotation resources"
            )

        return self

    @property
    def source_url_hash(self) -> str:
        """Return the SHA-256 identity of the normalized source URL."""

        return sha256(str(self.source_url).encode("utf-8")).hexdigest()

    @property
    def resource_id(self) -> str:
        """Return the stable logical identity stored in the run manifest."""

        if self.resource_type is BronzeResourceType.OCR_ANNOTATION_LIST:
            if self.canvas_index is None or self.annotation_index is None:
                raise RuntimeError("validated annotation position is missing")

            return (
                f"{self.resource_type.value}:{self.work_id}:"
                f"{self.canvas_index}:{self.annotation_index}:"
                f"{self.source_url_hash}"
            )

        return f"{self.resource_type.value}:{self.work_id}"

    @property
    def relative_path(self) -> PurePosixPath:
        """Return the portable location of this resource within its run."""

        work_directory = PurePosixPath("works") / self.work_id

        if self.resource_type is BronzeResourceType.CATALOGUE_WORK:
            return work_directory / "work.json"

        if self.resource_type is BronzeResourceType.IIIF_MANIFEST:
            return work_directory / "manifest.json"

        if self.canvas_index is None or self.annotation_index is None:
            raise RuntimeError("validated annotation position is missing")

        filename = (
            f"{self.canvas_index:06d}-"
            f"{self.annotation_index:02d}-"
            f"{self.source_url_hash[:12]}.json"
        )
        return work_directory / "annotations" / filename


class WellcomeBronzeParameters(BronzeModel):
    """Parameters that define a reproducible Wellcome acquisition."""

    limit: int = Field(ge=1, le=100)
    query: str | None = Field(default=None, min_length=1, max_length=500)
    language: Literal["eng"] = "eng"
    work_type: Literal["a"] = "a"
    availability: Literal["online"] = "online"
    licence: Literal["pdm"] = "pdm"
    location_type: Literal["iiif-presentation"] = "iiif-presentation"
    include: Literal["items,languages"] = "items,languages"


class BronzeResourceRecord(BronzeModel):
    """Provenance and integrity receipt for one stored raw file."""

    resource_id: str = Field(min_length=1, max_length=512)
    resource_type: BronzeResourceType
    work_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=_SAFE_IDENTIFIER_PATTERN,
    )
    relative_path: str = Field(min_length=1, max_length=1024)
    source_url: AnyHttpUrl
    acquired_at: AwareDatetime
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_length: int = Field(ge=1)
    content_type: str | None = Field(default=None, min_length=1, max_length=200)
    canvas_index: int | None = Field(default=None, ge=0)
    annotation_index: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_against_identity(self) -> Self:
        """Ensure recorded IDs and paths match the identity rules."""

        identity = BronzeResourceIdentity(
            resource_type=self.resource_type,
            work_id=self.work_id,
            source_url=self.source_url,
            canvas_index=self.canvas_index,
            annotation_index=self.annotation_index,
        )

        if self.resource_id != identity.resource_id:
            raise ValueError("resource_id does not match the resource identity")

        if self.relative_path != identity.relative_path.as_posix():
            raise ValueError("relative_path does not match the resource identity")

        return self


class BronzeFailureRecord(BronzeModel):
    """One source failure retained for inspection and later retry."""

    occurred_at: AwareDatetime
    work_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        pattern=_SAFE_IDENTIFIER_PATTERN,
    )
    resource_type: BronzeResourceType | None = None
    source_url: AnyHttpUrl
    error_type: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=2000)
    resolved_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_resolution_time(self) -> Self:
        """A failure cannot be resolved before it occurred."""

        if self.resolved_at is not None and self.resolved_at < self.occurred_at:
            raise ValueError("resolved_at cannot be earlier than occurred_at")

        return self


class BronzeRunManifest(BronzeModel):
    """Auditable acquisition ledger for one Bronze run."""

    schema_version: Literal[1] = 1
    identity: BronzeRunIdentity
    status: BronzeRunStatus
    pipeline_version: str = Field(min_length=1, max_length=100)
    parameters: WellcomeBronzeParameters
    catalogue_base_url: AnyHttpUrl

    started_at: AwareDatetime
    updated_at: AwareDatetime
    finished_at: AwareDatetime | None = None

    requested_work_count: int = Field(ge=1, le=100)
    discovered_work_count: int = Field(ge=0, le=100)
    completed_work_count: int = Field(ge=0, le=100)
    completed_work_ids: tuple[str, ...] = ()

    canvas_count: int = Field(default=0, ge=0)
    annotation_count: int = Field(default=0, ge=0)
    missing_ocr_page_count: int = Field(default=0, ge=0)

    resources: tuple[BronzeResourceRecord, ...] = ()
    failures: tuple[BronzeFailureRecord, ...] = ()

    @model_validator(mode="after")
    def validate_run_consistency(self) -> Self:
        """Reject internally inconsistent run metadata."""

        start_date = self.started_at.astimezone(UTC).date()
        if self.identity.ingestion_date != start_date:
            raise ValueError("ingestion_date must match the UTC date of started_at")

        if self.updated_at < self.started_at:
            raise ValueError("updated_at cannot be earlier than started_at")

        if self.status is BronzeRunStatus.RUNNING:
            if self.finished_at is not None:
                raise ValueError("a running run cannot have finished_at")
        elif self.finished_at is None:
            raise ValueError("a terminal run requires finished_at")

        if self.finished_at is not None:
            if self.finished_at < self.started_at:
                raise ValueError("finished_at cannot be earlier than started_at")
            if self.finished_at > self.updated_at:
                raise ValueError("updated_at cannot be earlier than finished_at")

        if self.requested_work_count != self.parameters.limit:
            raise ValueError("requested_work_count must match the requested limit")

        if self.discovered_work_count > self.requested_work_count:
            raise ValueError("discovered_work_count cannot exceed requested_work_count")

        if self.completed_work_count > self.discovered_work_count:
            raise ValueError("completed_work_count cannot exceed discovered_work_count")

        if self.completed_work_count != len(self.completed_work_ids):
            raise ValueError("completed_work_count must match completed_work_ids")

        if len(set(self.completed_work_ids)) != len(self.completed_work_ids):
            raise ValueError("completed_work_ids must be unique")

        if self.missing_ocr_page_count > self.canvas_count:
            raise ValueError("missing_ocr_page_count cannot exceed canvas_count")

        resource_ids = [resource.resource_id for resource in self.resources]
        if len(set(resource_ids)) != len(resource_ids):
            raise ValueError("resource IDs must be unique")

        resource_paths = [resource.relative_path for resource in self.resources]
        if len(set(resource_paths)) != len(resource_paths):
            raise ValueError("resource paths must be unique")

        stored_annotation_count = sum(
            resource.resource_type is BronzeResourceType.OCR_ANNOTATION_LIST
            for resource in self.resources
        )
        if self.annotation_count != stored_annotation_count:
            raise ValueError("annotation_count must match stored annotation resources")

        required_work_resources = {
            BronzeResourceType.CATALOGUE_WORK,
            BronzeResourceType.IIIF_MANIFEST,
        }
        for work_id in self.completed_work_ids:
            stored_types = {
                resource.resource_type
                for resource in self.resources
                if resource.work_id == work_id
            }
            if not required_work_resources.issubset(stored_types):
                raise ValueError(
                    f"completed work {work_id} is missing required raw resources"
                )

        unresolved_failures = [
            failure for failure in self.failures if failure.resolved_at is None
        ]

        if self.status is BronzeRunStatus.COMPLETED and unresolved_failures:
            raise ValueError("a completed run cannot contain unresolved failures")

        failure_statuses = {
            BronzeRunStatus.COMPLETED_WITH_FAILURES,
            BronzeRunStatus.FAILED,
        }
        if self.status in failure_statuses and not unresolved_failures:
            raise ValueError("a failed run status requires an unresolved failure")

        return self
