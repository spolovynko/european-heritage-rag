"""Typed models for Wellcome catalogue and IIIF source responses."""

from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field


class WellcomeSourceModel(BaseModel):
    """Base model for the Wellcome source data used by HeritageRAG."""

    model_config = ConfigDict(extra="ignore", frozen=True)


class IdentifierReference(WellcomeSourceModel):
    """Identifier from a Wellcome catalogue controlled value."""

    id: str = Field(min_length=1)


class LicenceReference(IdentifierReference):
    """Rights identifier and its optional human-readable URL."""

    url: AnyHttpUrl | None = None


class DigitalLocation(WellcomeSourceModel):
    """Digital location attached to a Wellcome catalogue item."""

    location_type: IdentifierReference = Field(alias="locationType")
    url: AnyHttpUrl | None = None
    licence: LicenceReference | None = Field(default=None, alias="license")


class CatalogueItem(WellcomeSourceModel):
    """Catalogue item containing its digital locations."""

    locations: tuple[DigitalLocation, ...] = ()


class CatalogueWork(WellcomeSourceModel):
    """Narrow work record returned by Wellcome discovery."""

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    work_type: IdentifierReference = Field(alias="workType")
    availabilities: tuple[IdentifierReference, ...] = ()
    languages: tuple[IdentifierReference, ...] = ()
    items: tuple[CatalogueItem, ...] = ()


class CatalogueWorksPage(WellcomeSourceModel):
    """One paginated response from the Wellcome works endpoint."""

    resource_type: Literal["ResultList"] = Field(alias="type")
    page_size: int = Field(alias="pageSize", ge=1)
    total_pages: int = Field(alias="totalPages", ge=0)
    total_results: int = Field(alias="totalResults", ge=0)
    results: tuple[CatalogueWork, ...] = ()
    next_page: AnyHttpUrl | None = Field(default=None, alias="nextPage")


class AnnotationListReference(WellcomeSourceModel):
    """Reference from a canvas to an OCR annotation list."""

    id: AnyHttpUrl = Field(alias="@id")
    resource_type: Literal["sc:AnnotationList"] = Field(alias="@type")


class IiifCanvas(WellcomeSourceModel):
    """One page-like canvas in a IIIF Presentation 2 manifest."""

    id: AnyHttpUrl = Field(alias="@id")
    resource_type: Literal["sc:Canvas"] = Field(alias="@type")
    label: str = Field(min_length=1)
    other_content: tuple[AnnotationListReference, ...] = Field(
        default=(),
        alias="otherContent",
    )


class IiifSequence(WellcomeSourceModel):
    """Ordered collection of canvases in a IIIF manifest."""

    canvases: tuple[IiifCanvas, ...] = ()


class IiifManifest(WellcomeSourceModel):
    """Subset of an IIIF Presentation 2 manifest needed for ingestion."""

    context: str = Field(alias="@context", min_length=1)
    id: AnyHttpUrl = Field(alias="@id")
    resource_type: Literal["sc:Manifest"] = Field(alias="@type")
    label: str = Field(min_length=1)
    sequences: tuple[IiifSequence, ...] = ()


class AnnotationBody(WellcomeSourceModel):
    """Body of an annotation, which may or may not contain OCR text."""

    resource_type: str | None = Field(default=None, alias="@type", min_length=1)
    format: str | None = None
    chars: str | None = None


class IiifAnnotation(WellcomeSourceModel):
    """One entry in a IIIF annotation list."""

    resource_type: str = Field(alias="@type", min_length=1)
    motivation: str | None = None
    resource: AnnotationBody
    on: str = Field(min_length=1)


class OcrAnnotationList(WellcomeSourceModel):
    """Ordered OCR annotations associated with a canvas."""

    context: str = Field(alias="@context", min_length=1)
    id: AnyHttpUrl = Field(alias="@id")
    resource_type: Literal["sc:AnnotationList"] = Field(alias="@type")
    resources: tuple[IiifAnnotation, ...] = ()


class TraversedPage(WellcomeSourceModel):
    """One canvas and the OCR text found while traversing it."""

    canvas_index: int = Field(ge=0)
    canvas_id: AnyHttpUrl
    label: str = Field(min_length=1)
    annotation_list_urls: tuple[AnyHttpUrl, ...] = ()
    ocr_lines: tuple[str, ...] = ()
    text: str | None = None


class TraversedWork(WellcomeSourceModel):
    """A discovered work after its manifest and canvases were traversed."""

    work_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    manifest_url: AnyHttpUrl
    pages: tuple[TraversedPage, ...] = ()
