"""Read-only HTTP inspection endpoints for complete Gold datasets."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from european_heritage_rag.core.config import AppSettings, get_settings
from european_heritage_rag.domain.gold import (
    GoldChunk,
    GoldDatasetManifest,
    GoldStatistics,
)
from european_heritage_rag.pipeline.gold_store import GoldFilesystemStore

router = APIRouter(prefix="/gold", tags=["gold"])


class GoldChunkSummary(BaseModel):
    """Bounded list record without full chunk text or nested page spans."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk_id: str
    work_id: str
    title: str
    chunk_index: int
    token_count: int
    page_sequence_start: int
    page_sequence_end: int
    page_label_start: str
    page_label_end: str
    overlap_previous_token_count: int


class GoldChunkList(BaseModel):
    """Paginated Gold chunk summaries."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1)
    items: tuple[GoldChunkSummary, ...]


class GoldWorkSummary(BaseModel):
    """One work represented by at least one Gold chunk."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    work_id: str
    title: str
    chunk_count: int = Field(ge=1)


@router.get(
    "/datasets",
    response_model=tuple[GoldDatasetManifest, ...],
    summary="List complete Gold datasets",
)
def list_gold_datasets(
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> tuple[GoldDatasetManifest, ...]:
    """Return newest-first complete Gold manifests."""

    return GoldFilesystemStore(settings.gold_data_directory).list_manifests()


@router.get(
    "/datasets/{dataset_id}",
    response_model=GoldDatasetManifest,
    summary="Inspect one Gold dataset",
)
def get_gold_dataset(
    dataset_id: str,
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> GoldDatasetManifest:
    """Return one complete Gold manifest."""

    return _manifest_or_404(settings, dataset_id)


@router.get(
    "/datasets/{dataset_id}/statistics",
    response_model=GoldStatistics,
    summary="Inspect Gold chunk statistics",
)
def get_gold_statistics(
    dataset_id: str,
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> GoldStatistics:
    """Return measured construction statistics, not retrieval quality."""

    _manifest_or_404(settings, dataset_id)
    return GoldFilesystemStore(settings.gold_data_directory).read_statistics(dataset_id)


@router.get(
    "/datasets/{dataset_id}/works",
    response_model=tuple[GoldWorkSummary, ...],
    summary="List works represented in Gold chunks",
)
def list_gold_works(
    dataset_id: str,
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> tuple[GoldWorkSummary, ...]:
    """Return stable work choices for the chunk inspector."""

    _manifest_or_404(settings, dataset_id)
    chunks = GoldFilesystemStore(settings.gold_data_directory).read_chunks(dataset_id)
    works: dict[str, tuple[str, int]] = {}
    for chunk in chunks:
        title, count = works.get(chunk.work_id, (chunk.title, 0))
        works[chunk.work_id] = (title, count + 1)
    return tuple(
        GoldWorkSummary(work_id=work_id, title=title, chunk_count=count)
        for work_id, (title, count) in sorted(works.items())
    )


@router.get(
    "/datasets/{dataset_id}/chunks",
    response_model=GoldChunkList,
    summary="List bounded Gold chunk summaries",
)
def list_gold_chunks(
    dataset_id: str,
    settings: Annotated[AppSettings, Depends(get_settings)],
    work_id: str | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> GoldChunkList:
    """Filter and paginate summaries without returning full chunk text."""

    _manifest_or_404(settings, dataset_id)
    chunks = GoldFilesystemStore(settings.gold_data_directory).read_chunks(dataset_id)
    filtered = tuple(
        chunk for chunk in chunks if work_id is None or chunk.work_id == work_id
    )
    selected = filtered[offset : offset + limit]
    return GoldChunkList(
        total=len(filtered),
        offset=offset,
        limit=limit,
        items=tuple(_summary(chunk) for chunk in selected),
    )


@router.get(
    "/datasets/{dataset_id}/chunks/{chunk_id}",
    response_model=GoldChunk,
    summary="Inspect one full Gold chunk",
)
def get_gold_chunk(
    dataset_id: str,
    chunk_id: str,
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> GoldChunk:
    """Return full text, page spans, overlap, images, and metadata."""

    _manifest_or_404(settings, dataset_id)
    chunk = next(
        (
            item
            for item in GoldFilesystemStore(settings.gold_data_directory).read_chunks(
                dataset_id
            )
            if item.chunk_id == chunk_id
        ),
        None,
    )
    if chunk is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gold chunk not found",
        )
    return chunk


def _summary(chunk: GoldChunk) -> GoldChunkSummary:
    return GoldChunkSummary(
        chunk_id=chunk.chunk_id,
        work_id=chunk.work_id,
        title=chunk.title,
        chunk_index=chunk.chunk_index,
        token_count=chunk.token_count,
        page_sequence_start=chunk.page_sequence_start,
        page_sequence_end=chunk.page_sequence_end,
        page_label_start=chunk.page_label_start,
        page_label_end=chunk.page_label_end,
        overlap_previous_token_count=chunk.overlap_previous_token_count,
    )


def _manifest_or_404(
    settings: AppSettings,
    dataset_id: str,
) -> GoldDatasetManifest:
    manifest = GoldFilesystemStore(settings.gold_data_directory).find_manifest(
        dataset_id
    )
    if manifest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gold dataset not found",
        )
    return manifest
