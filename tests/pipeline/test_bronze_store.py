"""Tests for immutable Bronze filesystem persistence."""

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from european_heritage_rag.pipeline.bronze import (
    BronzeResourceIdentity,
    BronzeResourceType,
    BronzeRunIdentity,
    BronzeRunManifest,
    BronzeRunStatus,
    WellcomeBronzeParameters,
)
from european_heritage_rag.pipeline.bronze_store import (
    BronzeContentConflictError,
    BronzeFilesystemStore,
    BronzeManifestIdentityError,
    BronzeWriteDisposition,
    sha256_hex,
)

_ACQUIRED_AT = datetime(2026, 7, 23, 9, 30, tzinfo=UTC)


def make_run_identity(run_id: str = "test-run") -> BronzeRunIdentity:
    """Return one stable fixture run."""

    return BronzeRunIdentity(
        ingestion_date=date(2026, 7, 23),
        run_id=run_id,
    )


def make_work_identity() -> BronzeResourceIdentity:
    """Return one stable fixture catalogue-work identity."""

    return BronzeResourceIdentity(
        resource_type=BronzeResourceType.CATALOGUE_WORK,
        work_id="b2492307x",
        source_url="https://example.test/catalogue/work.json",
    )


def make_running_manifest(
    run: BronzeRunIdentity | None = None,
) -> BronzeRunManifest:
    """Return one valid running manifest."""

    identity = run or make_run_identity()
    started_at = datetime(2026, 7, 23, 9, 0, tzinfo=UTC)
    return BronzeRunManifest(
        identity=identity,
        status=BronzeRunStatus.RUNNING,
        pipeline_version="0.1.0",
        parameters=WellcomeBronzeParameters(limit=5, query="cholera"),
        catalogue_base_url=("https://api.wellcomecollection.org/catalogue/v2/"),
        started_at=started_at,
        updated_at=started_at,
        requested_work_count=5,
        discovered_work_count=0,
        completed_work_count=0,
    )


def test_sha256_is_stable_and_content_sensitive() -> None:
    """Identical bytes should match and changed bytes should not."""

    first = b'{"id":"b2492307x"}'
    identical = b'{"id":"b2492307x"}'
    changed = b'{"id":"different"}'

    assert sha256_hex(first) == sha256_hex(identical)
    assert sha256_hex(first) != sha256_hex(changed)


def test_write_resource_creates_exact_bytes_and_receipt(
    tmp_path: Path,
) -> None:
    """A new resource should appear at its deterministic final path."""

    store = BronzeFilesystemStore(tmp_path / "bronze")
    run = make_run_identity()
    resource = make_work_identity()
    content = b'{"id":"b2492307x","title":"Example"}'

    result = store.write_resource(
        run=run,
        resource=resource,
        content=content,
        acquired_at=_ACQUIRED_AT,
        content_type="application/json",
    )
    destination = store.resource_path(run, resource)

    assert result.disposition is BronzeWriteDisposition.CREATED
    assert destination.read_bytes() == content
    assert result.record.relative_path == "works/b2492307x/work.json"
    assert result.record.content_sha256 == sha256_hex(content)
    assert result.record.byte_length == len(content)
    assert result.record.acquired_at == _ACQUIRED_AT


def test_identical_second_write_is_unchanged(tmp_path: Path) -> None:
    """Repeating the same resource should not create another file."""

    store = BronzeFilesystemStore(tmp_path / "bronze")
    run = make_run_identity()
    resource = make_work_identity()
    content = b'{"id":"b2492307x"}'

    first = store.write_resource(
        run=run,
        resource=resource,
        content=content,
        acquired_at=_ACQUIRED_AT,
        content_type="application/json",
    )
    second = store.write_resource(
        run=run,
        resource=resource,
        content=content,
        acquired_at=_ACQUIRED_AT,
        content_type="application/json",
    )

    stored_files = [path for path in store.root.rglob("*") if path.is_file()]

    assert first.disposition is BronzeWriteDisposition.CREATED
    assert second.disposition is BronzeWriteDisposition.UNCHANGED
    assert stored_files == [store.resource_path(run, resource)]


def test_changed_content_does_not_overwrite_existing_resource(
    tmp_path: Path,
) -> None:
    """The same identity with changed bytes should be a conflict."""

    store = BronzeFilesystemStore(tmp_path / "bronze")
    run = make_run_identity()
    resource = make_work_identity()
    original = b'{"version":1}'
    changed = b'{"version":2}'

    store.write_resource(
        run=run,
        resource=resource,
        content=original,
        acquired_at=_ACQUIRED_AT,
        content_type="application/json",
    )

    with pytest.raises(BronzeContentConflictError) as caught:
        store.write_resource(
            run=run,
            resource=resource,
            content=changed,
            acquired_at=_ACQUIRED_AT,
            content_type="application/json",
        )

    destination = store.resource_path(run, resource)

    assert destination.read_bytes() == original
    assert caught.value.path == destination
    assert caught.value.existing_sha256 == sha256_hex(original)
    assert caught.value.incoming_sha256 == sha256_hex(changed)


def test_failed_atomic_replacement_exposes_no_partial_resource(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failure before replacement must leave no final or temporary file."""

    store = BronzeFilesystemStore(tmp_path / "bronze")
    run = make_run_identity()
    resource = make_work_identity()

    def fail_replacement(
        temporary_path: Path,
        destination: Path,
    ) -> None:
        raise OSError(
            f"simulated replacement failure: {temporary_path} -> {destination}"
        )

    monkeypatch.setattr(store, "_replace", fail_replacement)

    with pytest.raises(OSError, match="simulated replacement failure"):
        store.write_resource(
            run=run,
            resource=resource,
            content=b'{"id":"b2492307x"}',
            acquired_at=_ACQUIRED_AT,
            content_type="application/json",
        )

    destination = store.resource_path(run, resource)
    temporary_files = list(destination.parent.glob(f".{destination.name}.*.tmp"))

    assert not destination.exists()
    assert temporary_files == []


def test_empty_resource_is_rejected_before_creating_directories(
    tmp_path: Path,
) -> None:
    """An empty HTTP body cannot become a valid Bronze JSON resource."""

    root = tmp_path / "bronze"
    store = BronzeFilesystemStore(root)

    with pytest.raises(ValueError, match="cannot be empty"):
        store.write_resource(
            run=make_run_identity(),
            resource=make_work_identity(),
            content=b"",
            acquired_at=_ACQUIRED_AT,
            content_type="application/json",
        )

    assert not root.exists()


def test_missing_manifest_returns_none(tmp_path: Path) -> None:
    """Reading before the first manifest write should be an honest absence."""

    store = BronzeFilesystemStore(tmp_path / "bronze")

    assert store.load_manifest(make_run_identity()) is None


def test_manifest_is_written_and_loaded_atomically(tmp_path: Path) -> None:
    """A complete serialized manifest should round-trip through the store."""

    store = BronzeFilesystemStore(tmp_path / "bronze")
    manifest = make_running_manifest()

    path = store.write_manifest(manifest)

    assert path == store.manifest_path(manifest.identity)
    assert path.read_bytes().endswith(b"\n")
    assert store.load_manifest(manifest.identity) == manifest


def test_manifest_update_replaces_complete_previous_version(
    tmp_path: Path,
) -> None:
    """A progressing run should replace its ledger with a complete new one."""

    store = BronzeFilesystemStore(tmp_path / "bronze")
    initial = make_running_manifest()
    store.write_manifest(initial)
    values = initial.model_dump()
    values.update(
        {
            "updated_at": initial.updated_at + timedelta(minutes=5),
            "discovered_work_count": 2,
        }
    )
    updated = BronzeRunManifest.model_validate(values)

    store.write_manifest(updated)

    assert store.load_manifest(initial.identity) == updated


def test_failed_manifest_replacement_preserves_previous_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed update must leave the previous complete ledger readable."""

    store = BronzeFilesystemStore(tmp_path / "bronze")
    initial = make_running_manifest()
    manifest_path = store.write_manifest(initial)
    original_bytes = manifest_path.read_bytes()
    values = initial.model_dump()
    values.update(
        {
            "updated_at": initial.updated_at + timedelta(minutes=5),
            "discovered_work_count": 2,
        }
    )
    updated = BronzeRunManifest.model_validate(values)

    def fail_replacement(
        temporary_path: Path,
        destination: Path,
    ) -> None:
        raise OSError(
            f"simulated replacement failure: {temporary_path} -> {destination}"
        )

    monkeypatch.setattr(store, "_replace", fail_replacement)

    with pytest.raises(OSError, match="simulated replacement failure"):
        store.write_manifest(updated)

    temporary_files = list(manifest_path.parent.glob(f".{manifest_path.name}.*.tmp"))
    assert manifest_path.read_bytes() == original_bytes
    assert store.load_manifest(initial.identity) == initial
    assert temporary_files == []


def test_manifest_identity_must_match_its_directory(
    tmp_path: Path,
) -> None:
    """A manifest cannot claim another run identity than its directory."""

    store = BronzeFilesystemStore(tmp_path / "bronze")
    expected_run = make_run_identity("expected-run")
    actual_manifest = make_running_manifest(make_run_identity("another-run"))
    path = store.manifest_path(expected_run)
    path.parent.mkdir(parents=True)
    path.write_text(
        f"{actual_manifest.model_dump_json(indent=2)}\n",
        encoding="utf-8",
    )

    with pytest.raises(BronzeManifestIdentityError) as caught:
        store.load_manifest(expected_run)

    assert caught.value.path == path
    assert caught.value.expected == expected_run
    assert caught.value.actual == actual_manifest.identity


def test_listing_manifests_verifies_directory_identity(tmp_path: Path) -> None:
    """Run discovery must not trust an identity claimed by the JSON body."""

    store = BronzeFilesystemStore(tmp_path / "bronze")
    expected_run = make_run_identity("expected-run")
    actual_manifest = make_running_manifest(make_run_identity("another-run"))
    path = store.manifest_path(expected_run)
    path.parent.mkdir(parents=True)
    path.write_text(
        f"{actual_manifest.model_dump_json(indent=2)}\n",
        encoding="utf-8",
    )

    with pytest.raises(BronzeManifestIdentityError):
        store.list_manifests()
