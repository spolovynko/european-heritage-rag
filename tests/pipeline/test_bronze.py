"""Tests for Bronze identities and portable paths."""

from datetime import UTC, date, datetime
from hashlib import sha256
from pathlib import PurePosixPath

import pytest
from pydantic import ValidationError

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


def test_run_identity_builds_partitioned_directory() -> None:
    """A run should map to a stable source, date, and run directory."""

    identity = BronzeRunIdentity(
        ingestion_date=date(2026, 7, 23),
        run_id="a81f9c",
    )

    assert identity.relative_directory == PurePosixPath(
        "wellcome/ingestion_date=2026-07-23/run_id=a81f9c"
    )


@pytest.mark.parametrize(
    ("resource_type", "expected_filename"),
    [
        (BronzeResourceType.CATALOGUE_WORK, "work.json"),
        (BronzeResourceType.IIIF_MANIFEST, "manifest.json"),
    ],
)
def test_work_level_resources_have_stable_paths(
    resource_type: BronzeResourceType,
    expected_filename: str,
) -> None:
    """Work and manifest resources should use fixed filenames."""

    identity = BronzeResourceIdentity(
        resource_type=resource_type,
        work_id="b2492307x",
        source_url="https://example.test/source.json",
    )

    assert identity.resource_id == f"{resource_type.value}:b2492307x"
    assert identity.relative_path == (
        PurePosixPath("works") / "b2492307x" / expected_filename
    )


def test_annotation_identity_uses_position_and_url_hash() -> None:
    """Annotation paths should be ordered, portable, and URL-specific."""

    source_url = "https://example.test/annotations/page-42.json"
    url_hash = sha256(source_url.encode("utf-8")).hexdigest()

    identity = BronzeResourceIdentity(
        resource_type=BronzeResourceType.OCR_ANNOTATION_LIST,
        work_id="b2492307x",
        source_url=source_url,
        canvas_index=42,
        annotation_index=0,
    )

    assert identity.resource_id == (f"ocr_annotation_list:b2492307x:42:0:{url_hash}")
    assert identity.relative_path == PurePosixPath(
        f"works/b2492307x/annotations/000042-00-{url_hash[:12]}.json"
    )


def test_different_annotation_urls_have_different_identities() -> None:
    """Distinct source URLs must not collide at the same canvas position."""

    first = BronzeResourceIdentity(
        resource_type=BronzeResourceType.OCR_ANNOTATION_LIST,
        work_id="b2492307x",
        source_url="https://example.test/annotations/first.json",
        canvas_index=42,
        annotation_index=0,
    )
    second = BronzeResourceIdentity(
        resource_type=BronzeResourceType.OCR_ANNOTATION_LIST,
        work_id="b2492307x",
        source_url="https://example.test/annotations/second.json",
        canvas_index=42,
        annotation_index=0,
    )

    assert first.resource_id != second.resource_id
    assert first.relative_path != second.relative_path


def test_annotation_requires_complete_position() -> None:
    """An OCR annotation cannot be identified without both positions."""

    with pytest.raises(ValidationError, match="require canvas_index"):
        BronzeResourceIdentity(
            resource_type=BronzeResourceType.OCR_ANNOTATION_LIST,
            work_id="b2492307x",
            source_url="https://example.test/annotations/page.json",
            canvas_index=42,
        )


def test_non_annotation_resource_rejects_page_position() -> None:
    """Canvas coordinates do not belong to work or manifest resources."""

    with pytest.raises(ValidationError, match="only valid"):
        BronzeResourceIdentity(
            resource_type=BronzeResourceType.IIIF_MANIFEST,
            work_id="b2492307x",
            source_url="https://example.test/manifest.json",
            canvas_index=0,
            annotation_index=0,
        )


def test_unsafe_work_identifier_is_rejected() -> None:
    """A source identifier must not be able to escape its run directory."""

    with pytest.raises(ValidationError):
        BronzeResourceIdentity(
            resource_type=BronzeResourceType.CATALOGUE_WORK,
            work_id="../outside",
            source_url="https://example.test/work.json",
        )


_STARTED_AT = datetime(2026, 7, 23, 9, 0, tzinfo=UTC)
_FINISHED_AT = datetime(2026, 7, 23, 10, 0, tzinfo=UTC)


def make_resource_record(
    resource_type: BronzeResourceType,
    *,
    source_url: str,
    content_hash_character: str,
) -> BronzeResourceRecord:
    """Create a valid resource receipt for one fixture work."""

    identity = BronzeResourceIdentity(
        resource_type=resource_type,
        work_id="b2492307x",
        source_url=source_url,
    )

    return BronzeResourceRecord(
        resource_id=identity.resource_id,
        resource_type=identity.resource_type,
        work_id=identity.work_id,
        relative_path=identity.relative_path.as_posix(),
        source_url=identity.source_url,
        acquired_at=_STARTED_AT,
        content_sha256=content_hash_character * 64,
        byte_length=128,
        content_type="application/json",
    )


def make_manifest_values() -> dict[str, object]:
    """Return a valid initial running-manifest payload."""

    return {
        "identity": BronzeRunIdentity(
            ingestion_date=date(2026, 7, 23),
            run_id="a81f9c",
        ),
        "status": BronzeRunStatus.RUNNING,
        "pipeline_version": "0.1.0",
        "parameters": WellcomeBronzeParameters(
            limit=5,
            query="cholera",
        ),
        "catalogue_base_url": ("https://api.wellcomecollection.org/catalogue/v2/"),
        "started_at": _STARTED_AT,
        "updated_at": _STARTED_AT,
        "requested_work_count": 5,
        "discovered_work_count": 0,
        "completed_work_count": 0,
    }


def test_resource_record_matches_identity_and_integrity() -> None:
    """A valid resource receipt should retain provenance and its hash."""

    record = make_resource_record(
        BronzeResourceType.CATALOGUE_WORK,
        source_url="https://example.test/catalogue/work.json",
        content_hash_character="a",
    )

    assert record.resource_id == "catalogue_work:b2492307x"
    assert record.relative_path == "works/b2492307x/work.json"
    assert record.content_sha256 == "a" * 64
    assert record.byte_length == 128


def test_resource_record_rejects_mismatched_path() -> None:
    """A manifest cannot point a resource identity at another path."""

    identity = BronzeResourceIdentity(
        resource_type=BronzeResourceType.IIIF_MANIFEST,
        work_id="b2492307x",
        source_url="https://example.test/manifest.json",
    )

    with pytest.raises(ValidationError, match="relative_path"):
        BronzeResourceRecord(
            resource_id=identity.resource_id,
            resource_type=identity.resource_type,
            work_id=identity.work_id,
            relative_path="works/b2492307x/work.json",
            source_url=identity.source_url,
            acquired_at=_STARTED_AT,
            content_sha256="a" * 64,
            byte_length=128,
            content_type="application/json",
        )


def test_running_manifest_accepts_consistent_initial_state() -> None:
    """A newly started run should be valid before discovery completes."""

    manifest = BronzeRunManifest(**make_manifest_values())

    assert manifest.schema_version == 1
    assert manifest.status is BronzeRunStatus.RUNNING
    assert manifest.parameters.query == "cholera"
    assert manifest.requested_work_count == 5
    assert manifest.resources == ()


def test_terminal_manifest_requires_finish_time() -> None:
    """A terminal run must record when it finished."""

    values = make_manifest_values()
    values["status"] = BronzeRunStatus.COMPLETED

    with pytest.raises(ValidationError, match="requires finished_at"):
        BronzeRunManifest(**values)


def test_completed_manifest_requires_work_and_manifest_resources() -> None:
    """A work cannot be complete when required raw files are absent."""

    values = make_manifest_values()
    values.update(
        {
            "status": BronzeRunStatus.COMPLETED,
            "updated_at": _FINISHED_AT,
            "finished_at": _FINISHED_AT,
            "discovered_work_count": 1,
            "completed_work_count": 1,
            "completed_work_ids": ("b2492307x",),
        }
    )

    with pytest.raises(ValidationError, match="missing required raw resources"):
        BronzeRunManifest(**values)


def test_completed_manifest_accepts_required_resources() -> None:
    """A completed work needs both its raw work and IIIF manifest."""

    work_record = make_resource_record(
        BronzeResourceType.CATALOGUE_WORK,
        source_url="https://example.test/catalogue/work.json",
        content_hash_character="a",
    )
    manifest_record = make_resource_record(
        BronzeResourceType.IIIF_MANIFEST,
        source_url="https://example.test/manifest.json",
        content_hash_character="b",
    )

    values = make_manifest_values()
    values.update(
        {
            "status": BronzeRunStatus.COMPLETED,
            "updated_at": _FINISHED_AT,
            "finished_at": _FINISHED_AT,
            "discovered_work_count": 1,
            "completed_work_count": 1,
            "completed_work_ids": ("b2492307x",),
            "resources": (work_record, manifest_record),
        }
    )

    manifest = BronzeRunManifest(**values)

    assert manifest.completed_work_count == 1
    assert len(manifest.resources) == 2


def test_completed_manifest_rejects_unresolved_failure() -> None:
    """A run with an unresolved source failure is not fully completed."""

    failure = BronzeFailureRecord(
        occurred_at=_STARTED_AT,
        work_id="b2492307x",
        resource_type=BronzeResourceType.OCR_ANNOTATION_LIST,
        source_url="https://example.test/annotations/page.json",
        error_type="HTTPStatusError",
        message="The source returned HTTP 503",
    )

    values = make_manifest_values()
    values.update(
        {
            "status": BronzeRunStatus.COMPLETED,
            "updated_at": _FINISHED_AT,
            "finished_at": _FINISHED_AT,
            "failures": (failure,),
        }
    )

    with pytest.raises(ValidationError, match="unresolved failures"):
        BronzeRunManifest(**values)
