"""Offline integrity and replay validation for Bronze runs."""

from json import JSONDecodeError, loads
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from european_heritage_rag.pipeline.bronze import (
    BronzeResourceIdentity,
    BronzeResourceType,
    BronzeRunManifest,
)
from european_heritage_rag.pipeline.bronze_store import (
    BronzeFilesystemStore,
    sha256_hex,
)
from european_heritage_rag.sources.wellcome.models import (
    CatalogueWork,
    IiifManifest,
    OcrAnnotationList,
)


class BronzeValidationIssue(BaseModel):
    """One actionable integrity problem discovered in a Bronze run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    relative_path: str | None = None
    resource_id: str | None = None


class BronzeValidationReport(BaseModel):
    """Machine-readable result of validating one Bronze run offline."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str = Field(min_length=1)
    checked_resource_count: int = Field(ge=0)
    issues: tuple[BronzeValidationIssue, ...] = ()

    @property
    def is_valid(self) -> bool:
        """Return whether every declared resource passed validation."""

        return not self.issues


def validate_bronze_run(
    store: BronzeFilesystemStore,
    manifest: BronzeRunManifest,
) -> BronzeValidationReport:
    """Validate declared files, hashes, JSON shapes, and inventory coverage."""

    issues: list[BronzeValidationIssue] = []
    expected_paths: set[str] = set()
    run_directory = store.run_directory(manifest.identity)

    for record in manifest.resources:
        expected_paths.add(record.relative_path)
        identity = BronzeResourceIdentity(
            resource_type=record.resource_type,
            work_id=record.work_id,
            source_url=record.source_url,
            canvas_index=record.canvas_index,
            annotation_index=record.annotation_index,
        )
        path = store.resource_path(manifest.identity, identity)
        if not path.is_file():
            issues.append(
                BronzeValidationIssue(
                    code="missing_resource",
                    message="Manifest-declared resource file is missing",
                    relative_path=record.relative_path,
                    resource_id=record.resource_id,
                )
            )
            continue

        content = path.read_bytes()
        if len(content) != record.byte_length:
            issues.append(
                BronzeValidationIssue(
                    code="byte_length_mismatch",
                    message=(
                        f"Expected {record.byte_length} bytes but found {len(content)}"
                    ),
                    relative_path=record.relative_path,
                    resource_id=record.resource_id,
                )
            )

        actual_hash = sha256_hex(content)
        if actual_hash != record.content_sha256:
            issues.append(
                BronzeValidationIssue(
                    code="content_hash_mismatch",
                    message=(
                        f"Expected SHA-256 {record.content_sha256} but found "
                        f"{actual_hash}"
                    ),
                    relative_path=record.relative_path,
                    resource_id=record.resource_id,
                )
            )

        _validate_json_resource(
            record.resource_type,
            content,
            record.relative_path,
            record.resource_id,
            issues,
        )

    if run_directory.is_dir():
        for path in run_directory.rglob("*.json"):
            relative_path = path.relative_to(run_directory).as_posix()
            if relative_path == "run-manifest.json":
                continue
            if relative_path not in expected_paths:
                issues.append(
                    BronzeValidationIssue(
                        code="unlisted_resource",
                        message="JSON file is not declared in the run manifest",
                        relative_path=relative_path,
                    )
                )

        for path in run_directory.rglob("*.tmp"):
            issues.append(
                BronzeValidationIssue(
                    code="temporary_file",
                    message="Incomplete temporary file remains in the run",
                    relative_path=path.relative_to(run_directory).as_posix(),
                )
            )

    return BronzeValidationReport(
        run_id=manifest.identity.run_id,
        checked_resource_count=len(manifest.resources),
        issues=tuple(issues),
    )


def _validate_json_resource(
    resource_type: BronzeResourceType,
    content: bytes,
    relative_path: str,
    resource_id: str,
    issues: list[BronzeValidationIssue],
) -> None:
    try:
        loads(content)
    except (JSONDecodeError, UnicodeDecodeError) as error:
        issues.append(
            BronzeValidationIssue(
                code="invalid_json",
                message=f"Resource is not valid UTF-8 JSON: {error}",
                relative_path=relative_path,
                resource_id=resource_id,
            )
        )
        return

    model_type: type[CatalogueWork] | type[IiifManifest] | type[OcrAnnotationList]
    if resource_type is BronzeResourceType.CATALOGUE_WORK:
        model_type = CatalogueWork
    elif resource_type is BronzeResourceType.IIIF_MANIFEST:
        model_type = IiifManifest
    else:
        model_type = OcrAnnotationList
    try:
        model_type.model_validate_json(content)
    except ValidationError as error:
        issues.append(
            BronzeValidationIssue(
                code="invalid_source_shape",
                message=(
                    f"Resource no longer validates as {model_type.__name__}: {error}"
                ),
                relative_path=relative_path,
                resource_id=resource_id,
            )
        )


def resource_path_from_record(
    store: BronzeFilesystemStore,
    manifest: BronzeRunManifest,
    resource_id: str,
) -> Path | None:
    """Resolve a manifest-declared resource ID to a safe local path."""

    record = next(
        (
            candidate
            for candidate in manifest.resources
            if candidate.resource_id == resource_id
        ),
        None,
    )
    if record is None:
        return None
    identity = BronzeResourceIdentity(
        resource_type=record.resource_type,
        work_id=record.work_id,
        source_url=record.source_url,
        canvas_index=record.canvas_index,
        annotation_index=record.annotation_index,
    )
    return store.resource_path(manifest.identity, identity)
