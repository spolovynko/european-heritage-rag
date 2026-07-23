"""Read-only HTTP inspection endpoints for complete Silver datasets."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from european_heritage_rag.core.config import AppSettings, get_settings
from european_heritage_rag.domain.silver import (
    PageQualityFlag,
    SilverDatasetManifest,
    SilverPage,
    SilverQualityReport,
    SilverWork,
)
from european_heritage_rag.pipeline.silver_store import SilverFilesystemStore

router = APIRouter(prefix="/silver", tags=["silver"])


class SilverPageSummary(BaseModel):
    """Bounded page-list record without full raw and clean OCR."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    page_id: str
    work_id: str
    sequence_number: int
    page_label: str
    ocr_quality: str
    quality_flags: tuple[str, ...]
    clean_word_count: int
    image_url: str | None


class SilverPageList(BaseModel):
    """Paginated Silver page summaries."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1)
    items: tuple[SilverPageSummary, ...]


@router.get(
    "/datasets",
    response_model=tuple[SilverDatasetManifest, ...],
    summary="List complete Silver datasets",
)
def list_silver_datasets(
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> tuple[SilverDatasetManifest, ...]:
    """Return newest-first complete Silver manifests."""

    return SilverFilesystemStore(settings.silver_data_directory).list_manifests()


@router.get(
    "/datasets/{dataset_id}",
    response_model=SilverDatasetManifest,
    summary="Inspect one Silver dataset",
)
def get_silver_dataset(
    dataset_id: str,
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> SilverDatasetManifest:
    """Return one complete dataset manifest."""

    return _manifest_or_404(settings, dataset_id)


@router.get(
    "/datasets/{dataset_id}/works",
    response_model=tuple[SilverWork, ...],
    summary="List canonical Silver works",
)
def list_silver_works(
    dataset_id: str,
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> tuple[SilverWork, ...]:
    """Return canonical works after confirming the dataset exists."""

    _manifest_or_404(settings, dataset_id)
    return SilverFilesystemStore(settings.silver_data_directory).read_works(dataset_id)


@router.get(
    "/datasets/{dataset_id}/pages",
    response_model=SilverPageList,
    summary="List bounded Silver page summaries",
)
def list_silver_pages(
    dataset_id: str,
    settings: Annotated[AppSettings, Depends(get_settings)],
    work_id: str | None = None,
    quality_flag: PageQualityFlag | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> SilverPageList:
    """Filter and paginate page summaries without returning full OCR text."""

    _manifest_or_404(settings, dataset_id)
    pages = SilverFilesystemStore(settings.silver_data_directory).read_pages(dataset_id)
    filtered = tuple(
        page
        for page in pages
        if (work_id is None or page.work_id == work_id)
        and (quality_flag is None or quality_flag in page.quality_flags)
    )
    selected = filtered[offset : offset + limit]
    return SilverPageList(
        total=len(filtered),
        offset=offset,
        limit=limit,
        items=tuple(
            SilverPageSummary(
                page_id=page.page_id,
                work_id=page.work_id,
                sequence_number=page.sequence_number,
                page_label=page.page_label,
                ocr_quality=page.ocr_quality.value,
                quality_flags=tuple(flag.value for flag in page.quality_flags),
                clean_word_count=page.clean_word_count,
                image_url=str(page.image_url) if page.image_url is not None else None,
            )
            for page in selected
        ),
    )


@router.get(
    "/datasets/{dataset_id}/pages/{page_id}",
    response_model=SilverPage,
    summary="Inspect one Silver page",
)
def get_silver_page(
    dataset_id: str,
    page_id: str,
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> SilverPage:
    """Return full raw, clean, quality, image, and lineage details."""

    _manifest_or_404(settings, dataset_id)
    page = next(
        (
            candidate
            for candidate in SilverFilesystemStore(
                settings.silver_data_directory
            ).read_pages(dataset_id)
            if candidate.page_id == page_id
        ),
        None,
    )
    if page is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Silver page not found",
        )
    return page


@router.get(
    "/datasets/{dataset_id}/quality",
    response_model=SilverQualityReport,
    summary="Inspect Silver quality evidence",
)
def get_silver_quality(
    dataset_id: str,
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> SilverQualityReport:
    """Return machine-readable aggregate quality evidence."""

    _manifest_or_404(settings, dataset_id)
    return SilverFilesystemStore(settings.silver_data_directory).read_quality(
        dataset_id
    )


def _manifest_or_404(
    settings: AppSettings,
    dataset_id: str,
) -> SilverDatasetManifest:
    manifest = SilverFilesystemStore(settings.silver_data_directory).find_manifest(
        dataset_id
    )
    if manifest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Silver dataset not found",
        )
    return manifest
