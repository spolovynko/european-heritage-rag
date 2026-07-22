"""Tests for Wellcome catalogue and IIIF source models."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from european_heritage_rag.sources.wellcome.models import (
    CatalogueWorksPage,
    IiifManifest,
    OcrAnnotationList,
)

_FIXTURE_DIRECTORY = Path(__file__).parents[2] / "fixtures" / "wellcome"


def read_fixture(filename: str) -> str:
    """Read a Wellcome JSON fixture."""

    return (_FIXTURE_DIRECTORY / filename).read_text(encoding="utf-8")


def test_catalogue_fixture_contains_eligible_work() -> None:
    """The catalogue model should expose fields needed for discovery."""

    page = CatalogueWorksPage.model_validate_json(read_fixture("catalogue_page.json"))

    assert page.total_results == 1

    work = page.results[0]
    location = work.items[0].locations[0]

    assert work.id == "xpxuaxuf"
    assert work.work_type.id == "a"
    assert tuple(language.id for language in work.languages) == ("eng",)
    assert location.location_type.id == "iiif-presentation"
    assert location.licence is not None
    assert location.licence.id == "pdm"
    assert str(location.url) == (
        "https://iiif.wellcomecollection.org/presentation/v2/b28041136"
    )


def test_manifest_fixture_preserves_canvas_order() -> None:
    """Canvases and missing OCR references should be represented safely."""

    manifest = IiifManifest.model_validate_json(read_fixture("iiif_manifest.json"))

    canvases = manifest.sequences[0].canvases

    assert tuple(canvas.label for canvas in canvases) == (
        "Front Cover",
        "Blank page",
    )
    assert len(canvases[0].other_content) == 1
    assert canvases[1].other_content == ()


def test_ocr_fixture_preserves_line_order() -> None:
    """OCR resources should retain their source ordering and text."""

    annotation_list = OcrAnnotationList.model_validate_json(
        read_fixture("ocr_annotation_list.json")
    )

    lines = tuple(
        annotation.resource.chars
        for annotation in annotation_list.resources
        if annotation.resource.chars is not None
    )

    assert lines == (
        "CHOLERA.",
        "PRACTICAL OBSERVATIONS",
    )


def test_unneeded_source_fields_are_ignored() -> None:
    """Fields outside our narrow model should not break validation."""

    page = CatalogueWorksPage.model_validate_json(read_fixture("catalogue_page.json"))

    assert page.results[0].work_type.model_dump() == {"id": "a"}


def test_physical_catalogue_location_may_omit_url() -> None:
    """Physical holdings should not invalidate an otherwise usable work."""

    payload = json.loads(read_fixture("catalogue_page.json"))
    payload["results"][0]["items"][0]["locations"].append(
        {
            "locationType": {
                "id": "closed-stores",
                "label": "Closed stores",
            }
        }
    )

    page = CatalogueWorksPage.model_validate(payload)

    assert page.results[0].items[0].locations[1].url is None


def test_wrong_manifest_type_is_rejected() -> None:
    """A response that is not a manifest should fail validation."""

    payload = json.loads(read_fixture("iiif_manifest.json"))
    payload["@type"] = "sc:Collection"

    with pytest.raises(ValidationError):
        IiifManifest.model_validate(payload)


def test_non_text_annotation_body_may_omit_type() -> None:
    """Picture resources should parse so OCR extraction can ignore them."""

    payload = json.loads(read_fixture("ocr_annotation_list.json"))
    payload["resources"].append(
        {
            "@type": "oa:Annotation",
            "resource": {
                "@id": "dctypes:Image",
                "label": "Picture",
            },
            "on": "https://example.test/canvas/1",
        }
    )

    annotation_list = OcrAnnotationList.model_validate(payload)

    assert annotation_list.resources[-1].resource.resource_type is None
