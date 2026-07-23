"""Tests for resumable Wellcome ingestion orchestration."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl

from european_heritage_rag.pipeline.bronze_store import BronzeFilesystemStore
from european_heritage_rag.pipeline.bronze_validation import validate_bronze_run
from european_heritage_rag.sources.wellcome.client import RawResourceObserver
from european_heritage_rag.sources.wellcome.ingestion import (
    IngestionCheckpoint,
    IngestionStateStore,
    WellcomeIngestionRunner,
    ingestion_fingerprint,
)
from european_heritage_rag.sources.wellcome.models import (
    CatalogueWork,
    CatalogueWorksPage,
    RawWellcomeResource,
    TraversedPage,
    TraversedWork,
)

_FIXTURE_DIRECTORY = Path(__file__).parents[2] / "fixtures" / "wellcome"
_MANIFEST_URL = "https://iiif.wellcomecollection.org/presentation/v2/b28041136"


class FakeIngestionClient:
    """Deterministic source client used by orchestration tests."""

    def __init__(
        self,
        works: tuple[CatalogueWork, ...],
        results: dict[str, TraversedWork | Exception] | None = None,
    ) -> None:
        self._works = works
        self._results = results or {}
        self.traversed_work_ids: list[str] = []
        self.discovery_arguments: tuple[int, str | None, str] | None = None

    @property
    def retry_count(self) -> int:
        return 0

    def discover_works(
        self,
        *,
        limit: int,
        query: str | None = None,
        language: str = "eng",
        raw_resource_observer: RawResourceObserver | None = None,
    ) -> tuple[CatalogueWork, ...]:
        self.discovery_arguments = (limit, query, language)
        works = self._works[:limit]
        if raw_resource_observer is not None:
            acquired_at = datetime.now(UTC)
            for work in works:
                raw_resource_observer(
                    RawWellcomeResource(
                        resource_type="catalogue_work",
                        work_id=work.id,
                        source_url=AnyHttpUrl("https://example.test/catalogue/works"),
                        content=work.model_dump_json(by_alias=True).encode(),
                        acquired_at=acquired_at,
                        content_type="application/json",
                    )
                )
        return works

    def traverse_work(self, work: CatalogueWork) -> TraversedWork:
        self.traversed_work_ids.append(work.id)
        result = self._results[work.id]
        if isinstance(result, Exception):
            raise result
        return result

    def traverse_work_with_resources(
        self,
        work: CatalogueWork,
        *,
        raw_resource_observer: RawResourceObserver | None = None,
    ) -> TraversedWork:
        result = self.traverse_work(work)
        if raw_resource_observer is not None:
            acquired_at = datetime.now(UTC)
            raw_resource_observer(
                RawWellcomeResource(
                    resource_type="iiif_manifest",
                    work_id=work.id,
                    source_url=AnyHttpUrl(_MANIFEST_URL),
                    content=(_FIXTURE_DIRECTORY / "iiif_manifest.json").read_bytes(),
                    acquired_at=acquired_at,
                    content_type="application/json",
                )
            )
            raw_resource_observer(
                RawWellcomeResource(
                    resource_type="ocr_annotation_list",
                    work_id=work.id,
                    source_url=AnyHttpUrl(
                        "https://iiif.example.org/annotations/page-1"
                    ),
                    content=(
                        _FIXTURE_DIRECTORY / "ocr_annotation_list.json"
                    ).read_bytes(),
                    acquired_at=acquired_at,
                    content_type="application/json",
                    canvas_index=0,
                    annotation_index=0,
                )
            )
        return result


def fixture_work(work_id: str) -> CatalogueWork:
    page = CatalogueWorksPage.model_validate_json(
        (_FIXTURE_DIRECTORY / "catalogue_page.json").read_text(encoding="utf-8")
    )
    return page.results[0].model_copy(
        update={
            "id": work_id,
            "title": f"Fixture work {work_id}",
        }
    )


def traversed_work(
    work: CatalogueWork,
    *,
    include_missing_ocr: bool = False,
) -> TraversedWork:
    pages = [
        TraversedPage(
            canvas_index=0,
            canvas_id=f"https://example.test/canvas/{work.id}/0",
            label="Page 1",
            ocr_lines=("First line",),
            text="First line",
        )
    ]
    if include_missing_ocr:
        pages.append(
            TraversedPage(
                canvas_index=1,
                canvas_id=f"https://example.test/canvas/{work.id}/1",
                label="Page 2",
            )
        )

    return TraversedWork(
        work_id=work.id,
        title=work.title,
        manifest_url=_MANIFEST_URL,
        pages=tuple(pages),
    )


def test_state_store_returns_idle_status_before_first_run(tmp_path: Path) -> None:
    store = IngestionStateStore(tmp_path)

    status = store.load_status()

    assert status.status == "idle"
    assert status.run_id is None


def test_dry_run_discovers_without_traversal_or_checkpoint(tmp_path: Path) -> None:
    work = fixture_work("dry-run-work")
    client = FakeIngestionClient((work,))
    store = IngestionStateStore(tmp_path)
    runner = WellcomeIngestionRunner(client, store)

    status = runner.run(
        limit=1,
        query=" cholera ",
        dry_run=True,
    )

    assert status.status == "completed"
    assert status.query == "cholera"
    assert status.works_discovered == 1
    assert status.works_completed == 0
    assert client.discovery_arguments == (1, "cholera", "eng")
    assert client.traversed_work_ids == []
    assert store.status_path.is_file()
    assert not store.checkpoint_path.exists()


def test_run_checkpoints_success_and_terminal_failure(tmp_path: Path) -> None:
    first_work = fixture_work("successful-work")
    second_work = fixture_work("failed-work")
    client = FakeIngestionClient(
        (first_work, second_work),
        {
            first_work.id: traversed_work(
                first_work,
                include_missing_ocr=True,
            ),
            second_work.id: RuntimeError("annotation unavailable"),
        },
    )
    store = IngestionStateStore(tmp_path)
    runner = WellcomeIngestionRunner(client, store)

    status = runner.run(limit=2)
    checkpoint = store.load_checkpoint()

    assert status.status == "completed_with_failures"
    assert status.works_discovered == 2
    assert status.works_completed == 1
    assert status.pages_downloaded == 2
    assert status.missing_ocr_pages == 1
    assert status.failure_count == 1
    assert "failed-work" in status.failures
    assert checkpoint is not None
    assert checkpoint.completed_work_ids == ("successful-work",)
    assert "failed-work" in checkpoint.failures


def test_resume_skips_completed_work_and_retries_remaining_work(
    tmp_path: Path,
) -> None:
    first_work = fixture_work("first-work")
    second_work = fixture_work("second-work")
    fingerprint = ingestion_fingerprint(limit=2, query=None, language="eng")
    store = IngestionStateStore(tmp_path)
    store.save_checkpoint(
        IngestionCheckpoint(
            fingerprint=fingerprint,
            run_id="existing-run",
            started_at=datetime.now(UTC),
            completed_work_ids=(first_work.id,),
            pages_downloaded=1,
            failures={second_work.id: "previous failure"},
        )
    )
    client = FakeIngestionClient(
        (first_work, second_work),
        {second_work.id: traversed_work(second_work)},
    )
    runner = WellcomeIngestionRunner(client, store)

    status = runner.run(limit=2, resume=True)

    assert status.status == "completed"
    assert status.run_id == "existing-run"
    assert status.resumed is True
    assert status.works_completed == 2
    assert status.pages_downloaded == 2
    assert status.failure_count == 0
    assert client.traversed_work_ids == ["second-work"]


def test_resume_rejects_changed_options(tmp_path: Path) -> None:
    store = IngestionStateStore(tmp_path)
    store.save_checkpoint(
        IngestionCheckpoint(
            fingerprint=ingestion_fingerprint(
                limit=1,
                query="cholera",
                language="eng",
            ),
            run_id="existing-run",
            started_at=datetime.now(UTC),
        )
    )
    runner = WellcomeIngestionRunner(FakeIngestionClient(()), store)

    with pytest.raises(ValueError, match="do not match"):
        runner.run(
            limit=1,
            query="sanitation",
            resume=True,
        )


def test_run_persists_valid_bronze_and_resume_creates_no_duplicates(
    tmp_path: Path,
) -> None:
    """A completed work should be replayable and idempotent from Bronze."""

    work = fixture_work("bronze-work")
    state_store = IngestionStateStore(tmp_path / "state")
    bronze_store = BronzeFilesystemStore(tmp_path / "bronze")
    runner = WellcomeIngestionRunner(
        FakeIngestionClient(
            (work,),
            {work.id: traversed_work(work)},
        ),
        state_store,
        bronze_store,
    )

    status = runner.run(limit=1, query="cholera")
    assert status.run_id is not None
    manifest = bronze_store.find_manifest(status.run_id)
    assert manifest is not None
    report = validate_bronze_run(bronze_store, manifest)
    resource_paths = tuple(record.relative_path for record in manifest.resources)

    assert report.is_valid
    assert status.started_at is not None
    assert manifest.identity.ingestion_date == status.started_at.astimezone(UTC).date()
    assert manifest.completed_work_ids == ("bronze-work",)
    assert len(manifest.resources) == 3

    resumed = WellcomeIngestionRunner(
        FakeIngestionClient((work,), {}),
        state_store,
        bronze_store,
    ).run(limit=1, query="cholera", resume=True)
    resumed_manifest = bronze_store.find_manifest(status.run_id)

    assert resumed.status == "completed"
    assert resumed_manifest is not None
    assert (
        tuple(record.relative_path for record in resumed_manifest.resources)
        == resource_paths
    )
