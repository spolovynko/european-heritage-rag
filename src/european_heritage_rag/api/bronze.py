"""Read-only HTTP inspection endpoints for Bronze data."""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from european_heritage_rag.core.config import AppSettings, get_settings
from european_heritage_rag.pipeline.bronze import BronzeRunManifest
from european_heritage_rag.pipeline.bronze_store import BronzeFilesystemStore

router = APIRouter(prefix="/bronze", tags=["bronze"])


@router.get(
    "/runs",
    response_model=tuple[BronzeRunManifest, ...],
    summary="List Bronze acquisition runs",
)
def list_bronze_runs(
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> tuple[BronzeRunManifest, ...]:
    """Return newest-first validated run manifests."""

    return BronzeFilesystemStore(settings.bronze_data_directory).list_manifests()


@router.get(
    "/runs/{run_id}",
    response_model=BronzeRunManifest,
    summary="Inspect one Bronze acquisition run",
)
def get_bronze_run(
    run_id: str,
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> BronzeRunManifest:
    """Return one run ledger or a normal not-found response."""

    manifest = BronzeFilesystemStore(settings.bronze_data_directory).find_manifest(
        run_id
    )
    if manifest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bronze run not found",
        )
    return manifest


@router.get(
    "/runs/{run_id}/resources/{resource_id}",
    response_class=JSONResponse,
    summary="Preview one raw Bronze JSON resource",
)
def get_bronze_resource(
    run_id: str,
    resource_id: str,
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> JSONResponse:
    """Resolve a manifest resource ID and return its stored JSON."""

    store = BronzeFilesystemStore(settings.bronze_data_directory)
    manifest = store.find_manifest(run_id)
    if manifest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bronze run not found",
        )
    content = store.read_resource(manifest, resource_id)
    if content is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bronze resource not found",
        )
    return JSONResponse(content=json.loads(content))
