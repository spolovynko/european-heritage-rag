"""Tests for the Wellcome HTTP client."""

import json
from pathlib import Path

import httpx2
import pytest
import respx
from pydantic import ValidationError

from european_heritage_rag.core.config import AppSettings
from european_heritage_rag.sources.wellcome.client import (
    WellcomeClient,
    WellcomeStructureError,
)
from european_heritage_rag.sources.wellcome.models import (
    CatalogueWorksPage,
    RawWellcomeResource,
)

_FIXTURE_DIRECTORY = Path(__file__).parents[2] / "fixtures" / "wellcome"


def test_fetch_catalogue_page_uses_settings_and_parses_response(
    httpx2_mock: respx.Router,
) -> None:
    """The client should configure the request and validate its response."""

    route = httpx2_mock.get(
        "https://api.wellcomecollection.org/catalogue/v2/works",
        params={
            "pageSize": "1",
            "include": "items,languages",
        },
    ).respond(
        content=(_FIXTURE_DIRECTORY / "catalogue_page.json").read_text(encoding="utf-8")
    )

    settings = AppSettings(
        _env_file=None,
        wellcome_user_agent="HeritageRAG/test",
        wellcome_connect_timeout_seconds=2.0,
        wellcome_read_timeout_seconds=3.0,
        wellcome_write_timeout_seconds=4.0,
        wellcome_pool_timeout_seconds=5.0,
    )

    with WellcomeClient(settings) as client:
        page = client.fetch_catalogue_page(
            params={
                "pageSize": 1,
                "include": "items,languages",
            }
        )

    assert page.results[0].id == "xpxuaxuf"
    assert route.called

    request = route.calls.last.request

    assert request.headers["user-agent"] == "HeritageRAG/test"
    assert request.extensions["timeout"] == {
        "connect": 2.0,
        "read": 3.0,
        "write": 4.0,
        "pool": 5.0,
    }


def test_transient_status_is_retried(
    httpx2_mock: respx.Router,
) -> None:
    """A temporary server failure should be retried."""

    delays: list[float] = []

    route = httpx2_mock.get(
        "https://api.wellcomecollection.org/catalogue/v2/works",
        params={
            "pageSize": "1",
            "include": "items,languages",
        },
    ).mock(
        side_effect=[
            respx.MockResponse(503),
            respx.MockResponse(
                200,
                content=(_FIXTURE_DIRECTORY / "catalogue_page.json").read_text(
                    encoding="utf-8"
                ),
            ),
        ]
    )

    settings = AppSettings(
        _env_file=None,
        wellcome_max_attempts=2,
        wellcome_max_retry_wait_seconds=0.001,
    )

    with WellcomeClient(settings, sleep=delays.append) as client:
        page = client.fetch_catalogue_page(
            params={
                "pageSize": 1,
                "include": "items,languages",
            }
        )

    assert page.results[0].id == "xpxuaxuf"
    assert len(route.calls) == 2
    assert delays == [0.001]


@pytest.mark.parametrize(
    ("retry_after", "maximum_wait", "expected_wait"),
    [
        ("3", 8.0, 3.0),
        ("30", 8.0, 8.0),
        ("invalid", 8.0, 1.0),
        ("-1", 8.0, 1.0),
    ],
)
def test_retry_after_header_selects_wait(
    httpx2_mock: respx.Router,
    retry_after: str,
    maximum_wait: float,
    expected_wait: float,
) -> None:
    """Use valid server delays and fall back safely for invalid values."""

    delays: list[float] = []
    route = httpx2_mock.get(
        "https://api.wellcomecollection.org/catalogue/v2/works",
        params={
            "pageSize": "1",
            "include": "items,languages",
        },
    ).mock(
        side_effect=[
            respx.MockResponse(
                429,
                headers={"Retry-After": retry_after},
            ),
            respx.MockResponse(
                200,
                content=(_FIXTURE_DIRECTORY / "catalogue_page.json").read_text(
                    encoding="utf-8"
                ),
            ),
        ]
    )

    settings = AppSettings(
        _env_file=None,
        wellcome_max_attempts=2,
        wellcome_max_retry_wait_seconds=maximum_wait,
    )

    with WellcomeClient(settings, sleep=delays.append) as client:
        page = client.fetch_catalogue_page(
            params={
                "pageSize": 1,
                "include": "items,languages",
            }
        )

    assert page.results[0].id == "xpxuaxuf"
    assert len(route.calls) == 2
    assert delays == [expected_wait]


def test_permanent_status_is_not_retried(
    httpx2_mock: respx.Router,
) -> None:
    """A permanent invalid request should fail after one attempt."""

    route = httpx2_mock.get(
        "https://api.wellcomecollection.org/catalogue/v2/works",
        params={
            "pageSize": "1",
            "include": "items,languages",
        },
    ).respond(status_code=400)

    settings = AppSettings(
        _env_file=None,
        wellcome_max_attempts=4,
        wellcome_max_retry_wait_seconds=0.001,
    )

    with WellcomeClient(settings) as client:
        with pytest.raises(httpx2.HTTPStatusError):
            client.fetch_catalogue_page(
                params={
                    "pageSize": 1,
                    "include": "items,languages",
                }
            )

    assert len(route.calls) == 1


def test_discover_works_follows_pages_and_stops_at_limit(
    httpx2_mock: respx.Router,
) -> None:
    """Discovery should preserve order and stop without fetching another page."""

    second_page_url = "https://api.wellcomecollection.org/catalogue/v2/works?page=2"
    unused_third_page_url = (
        "https://api.wellcomecollection.org/catalogue/v2/works?page=3"
    )

    first_page = json.loads(
        (_FIXTURE_DIRECTORY / "catalogue_page.json").read_text(encoding="utf-8")
    )
    first_page["results"][0]["id"] = "first-work"
    first_page["totalPages"] = 3
    first_page["totalResults"] = 3
    first_page["nextPage"] = second_page_url

    second_page = json.loads(
        (_FIXTURE_DIRECTORY / "catalogue_page.json").read_text(encoding="utf-8")
    )
    second_page["results"][0]["id"] = "second-work"
    second_page["totalPages"] = 3
    second_page["totalResults"] = 3
    second_page["nextPage"] = unused_third_page_url

    first_route = httpx2_mock.get(
        "https://api.wellcomecollection.org/catalogue/v2/works",
        params={
            "workType": "a",
            "availabilities": "online",
            "items.locations.license": "pdm",
            "items.locations.locationType": "iiif-presentation",
            "languages": "eng",
            "include": "items,languages",
            "pageSize": "2",
            "query": "cholera",
        },
    ).respond(json=first_page)
    second_route = httpx2_mock.get(second_page_url).respond(json=second_page)

    settings = AppSettings(_env_file=None)

    with WellcomeClient(settings) as client:
        works = client.discover_works(
            limit=2,
            query="cholera",
        )

    assert tuple(work.id for work in works) == (
        "first-work",
        "second-work",
    )
    assert len(first_route.calls) == 1
    assert len(second_route.calls) == 1


def test_discover_works_rejects_non_public_domain_location(
    httpx2_mock: respx.Router,
) -> None:
    """Discovery should reject a work that fails local licence validation."""

    page = json.loads(
        (_FIXTURE_DIRECTORY / "catalogue_page.json").read_text(encoding="utf-8")
    )
    page["results"][0]["items"][0]["locations"][0]["license"]["id"] = "cc-by"

    route = httpx2_mock.get(
        "https://api.wellcomecollection.org/catalogue/v2/works",
        params={
            "workType": "a",
            "availabilities": "online",
            "items.locations.license": "pdm",
            "items.locations.locationType": "iiif-presentation",
            "languages": "eng",
            "include": "items,languages",
            "pageSize": "1",
        },
    ).respond(json=page)

    settings = AppSettings(_env_file=None)

    with WellcomeClient(settings) as client:
        works = client.discover_works(limit=1)

    assert works == ()
    assert len(route.calls) == 1


def test_discovery_exposes_lossless_selected_work_json(
    httpx2_mock: respx.Router,
) -> None:
    """Bronze capture must preserve fields outside the narrow source model."""

    page = json.loads(
        (_FIXTURE_DIRECTORY / "catalogue_page.json").read_text(encoding="utf-8")
    )
    page["results"][0]["futureSourceField"] = {
        "preserved": True,
        "label": "not used by Phase 4",
    }
    httpx2_mock.get(
        "https://api.wellcomecollection.org/catalogue/v2/works",
        params={
            "workType": "a",
            "availabilities": "online",
            "items.locations.license": "pdm",
            "items.locations.locationType": "iiif-presentation",
            "languages": "eng",
            "include": "items,languages",
            "pageSize": "1",
        },
    ).respond(json=page)
    captured: list[RawWellcomeResource] = []

    with WellcomeClient(AppSettings(_env_file=None)) as client:
        works = client.discover_works(
            limit=1,
            raw_resource_observer=captured.append,
        )

    raw_work = json.loads(captured[0].content)
    assert works[0].id == "xpxuaxuf"
    assert captured[0].resource_type == "catalogue_work"
    assert captured[0].work_id == "xpxuaxuf"
    assert raw_work["futureSourceField"]["preserved"] is True


def test_traverse_work_preserves_canvas_and_ocr_order(
    httpx2_mock: respx.Router,
) -> None:
    """Traversal should retain canvas identity and exact OCR line ordering."""

    work = CatalogueWorksPage.model_validate_json(
        (_FIXTURE_DIRECTORY / "catalogue_page.json").read_text(encoding="utf-8")
    ).results[0]
    manifest_url = "https://iiif.wellcomecollection.org/presentation/v2/b28041136"
    annotation_url = (
        "https://iiif.wellcomecollection.org/annotations/v2/"
        "b28041136/b28041136_0001.jp2/line"
    )

    httpx2_mock.get(manifest_url).respond(
        content=(_FIXTURE_DIRECTORY / "iiif_manifest.json").read_text(encoding="utf-8")
    )
    httpx2_mock.get(annotation_url).respond(
        content=(_FIXTURE_DIRECTORY / "ocr_annotation_list.json").read_text(
            encoding="utf-8"
        )
    )

    settings = AppSettings(_env_file=None)

    with WellcomeClient(settings) as client:
        traversed = client.traverse_work(work)

    assert traversed.work_id == "xpxuaxuf"
    assert str(traversed.manifest_url) == manifest_url
    assert tuple(page.canvas_index for page in traversed.pages) == (0, 1)
    assert tuple(page.label for page in traversed.pages) == (
        "Front Cover",
        "Blank page",
    )
    assert traversed.pages[0].ocr_lines == (
        "CHOLERA.",
        "PRACTICAL OBSERVATIONS",
    )
    assert traversed.pages[0].text == "CHOLERA.\nPRACTICAL OBSERVATIONS"
    assert traversed.pages[1].annotation_list_urls == ()
    assert traversed.pages[1].text is None


def test_traversal_exposes_exact_manifest_and_annotation_bytes(
    httpx2_mock: respx.Router,
) -> None:
    """Validated IIIF payloads should remain available for Bronze storage."""

    work = CatalogueWorksPage.model_validate_json(
        (_FIXTURE_DIRECTORY / "catalogue_page.json").read_text(encoding="utf-8")
    ).results[0]
    manifest_url = "https://iiif.wellcomecollection.org/presentation/v2/b28041136"
    annotation_url = (
        "https://iiif.wellcomecollection.org/annotations/v2/"
        "b28041136/b28041136_0001.jp2/line"
    )
    manifest_content = (_FIXTURE_DIRECTORY / "iiif_manifest.json").read_bytes()
    annotation_content = (_FIXTURE_DIRECTORY / "ocr_annotation_list.json").read_bytes()
    httpx2_mock.get(manifest_url).respond(content=manifest_content)
    httpx2_mock.get(annotation_url).respond(content=annotation_content)
    captured: list[RawWellcomeResource] = []

    with WellcomeClient(AppSettings(_env_file=None)) as client:
        client.traverse_work_with_resources(
            work,
            raw_resource_observer=captured.append,
        )

    assert tuple(resource.resource_type for resource in captured) == (
        "iiif_manifest",
        "ocr_annotation_list",
    )
    assert captured[0].content == manifest_content
    assert captured[1].content == annotation_content
    assert captured[1].canvas_index == 0
    assert captured[1].annotation_index == 0


def test_traversal_exposes_invalid_manifest_before_validation(
    httpx2_mock: respx.Router,
) -> None:
    """A malformed source response should still be available for diagnosis."""

    work = CatalogueWorksPage.model_validate_json(
        (_FIXTURE_DIRECTORY / "catalogue_page.json").read_text(encoding="utf-8")
    ).results[0]
    manifest_url = "https://iiif.wellcomecollection.org/presentation/v2/b28041136"
    invalid_content = b'{"unexpected":true}'
    httpx2_mock.get(manifest_url).respond(content=invalid_content)
    captured: list[RawWellcomeResource] = []

    with WellcomeClient(AppSettings(_env_file=None)) as client:
        with pytest.raises(ValidationError):
            client.traverse_work_with_resources(
                work,
                raw_resource_observer=captured.append,
            )

    assert len(captured) == 1
    assert captured[0].resource_type == "iiif_manifest"
    assert captured[0].content == invalid_content


def test_traverse_work_treats_referenced_ocr_error_as_failure(
    httpx2_mock: respx.Router,
) -> None:
    """A terminal error for a referenced annotation list should fail the work."""

    work = CatalogueWorksPage.model_validate_json(
        (_FIXTURE_DIRECTORY / "catalogue_page.json").read_text(encoding="utf-8")
    ).results[0]
    manifest_url = "https://iiif.wellcomecollection.org/presentation/v2/b28041136"
    annotation_url = (
        "https://iiif.wellcomecollection.org/annotations/v2/"
        "b28041136/b28041136_0001.jp2/line"
    )

    httpx2_mock.get(manifest_url).respond(
        content=(_FIXTURE_DIRECTORY / "iiif_manifest.json").read_text(encoding="utf-8")
    )
    annotation_route = httpx2_mock.get(annotation_url).respond(status_code=404)

    settings = AppSettings(
        _env_file=None,
        wellcome_max_retry_wait_seconds=0.001,
    )

    with WellcomeClient(settings) as client:
        with pytest.raises(httpx2.HTTPStatusError):
            client.traverse_work(work)

    assert len(annotation_route.calls) == 1


def test_traverse_work_rejects_manifest_without_sequence(
    httpx2_mock: respx.Router,
) -> None:
    """A manifest without its default sequence should fail structurally."""

    work = CatalogueWorksPage.model_validate_json(
        (_FIXTURE_DIRECTORY / "catalogue_page.json").read_text(encoding="utf-8")
    ).results[0]
    manifest = json.loads(
        (_FIXTURE_DIRECTORY / "iiif_manifest.json").read_text(encoding="utf-8")
    )
    manifest["sequences"] = []

    httpx2_mock.get(
        "https://iiif.wellcomecollection.org/presentation/v2/b28041136"
    ).respond(json=manifest)

    settings = AppSettings(_env_file=None)

    with WellcomeClient(settings) as client:
        with pytest.raises(WellcomeStructureError, match="no default sequence"):
            client.traverse_work(work)
