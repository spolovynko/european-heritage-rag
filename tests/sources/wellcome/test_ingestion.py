"""Tests for resumable Wellcome ingestion orchestration."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from european_heritage_rag.sources.wellcome.ingestion import (
    IngestionCheckpoint,
    IngestionStateStore,
    WellcomeIngestionRunner,
    ingestion_fingerprint,
)
from european_heritage_rag.sources.wellcome.models import (
    CatalogueWork,
    CatalogueWorksPage,
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
    ) -> tuple[CatalogueWork, ...]:
        self.discovery_arguments = (limit, query, language)
        return self._works[:limit]

    def traverse_work(self, work: CatalogueWork) -> TraversedWork:
        self.traversed_work_ids.append(work.id)
        result = self._results[work.id]
        if isinstance(result, Exception):
            raise result
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
