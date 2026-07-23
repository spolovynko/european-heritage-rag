"""Command-line interface for HeritageRAG."""

from importlib.metadata import version
from typing import Annotated

import typer

from european_heritage_rag.core.config import get_settings
from european_heritage_rag.pipeline.bronze_store import (
    BronzeFilesystemStore,
    BronzeManifestIdentityError,
)
from european_heritage_rag.pipeline.bronze_validation import validate_bronze_run
from european_heritage_rag.sources.wellcome.ingestion import run_wellcome_ingestion

_DISTRIBUTION_NAME = "european-heritage-rag"

app = typer.Typer(
    name="european-heritage-rag",
    help="Operate and inspect the HeritageRAG application.",
    no_args_is_help=True,
)
ingest_app = typer.Typer(
    help="Discover and traverse external heritage sources.",
    no_args_is_help=True,
)
bronze_app = typer.Typer(
    help="Inspect and validate immutable raw source runs.",
    no_args_is_help=True,
)
app.add_typer(ingest_app, name="ingest")
app.add_typer(bronze_app, name="bronze")


@app.callback()
def cli() -> None:
    """Provide HeritageRAG command-line operations."""


@app.command("version")
def show_version() -> None:
    """Print the installed HeritageRAG version."""

    typer.echo(version(_DISTRIBUTION_NAME))


@ingest_app.command("wellcome")
def ingest_wellcome(
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            min=1,
            max=100,
            help="Maximum eligible works to discover.",
        ),
    ] = 5,
    query: Annotated[
        str | None,
        typer.Option(
            "--query",
            help="Optional Wellcome full-text discovery query.",
        ),
    ] = None,
    language: Annotated[
        str,
        typer.Option(
            "--language",
            help="Discovery language; Phase 4 supports eng only.",
        ),
    ] = "eng",
    resume: Annotated[
        bool,
        typer.Option(
            "--resume",
            help="Continue the matching Wellcome checkpoint.",
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Discover works without requesting manifests or OCR.",
        ),
    ] = False,
) -> None:
    """Discover and sequentially traverse public-domain Wellcome books."""

    if resume and dry_run:
        raise typer.BadParameter("--resume and --dry-run cannot be used together")
    if language != "eng":
        raise typer.BadParameter("--language must be eng during Phase 4")

    try:
        result = run_wellcome_ingestion(
            get_settings(),
            limit=limit,
            query=query,
            language=language,
            resume=resume,
            dry_run=dry_run,
        )
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error
    except Exception as error:
        typer.echo(f"Wellcome ingestion failed: {error}", err=True)
        raise typer.Exit(code=1) from error

    typer.echo(f"Run: {result.run_id}")
    typer.echo(f"Status: {result.status}")
    typer.echo(f"Works: {result.works_completed}/{result.works_discovered}")
    typer.echo(f"Pages traversed: {result.pages_downloaded}")
    typer.echo(f"Missing OCR pages: {result.missing_ocr_pages}")
    typer.echo(f"Retries: {result.retry_count}; failures: {result.failure_count}")


@bronze_app.command("inspect")
def inspect_bronze(
    run_id: Annotated[
        str | None,
        typer.Option(
            "--run-id",
            help="Show one run in detail; omit to list every run.",
        ),
    ] = None,
) -> None:
    """Show Bronze runs, counts, failures, paths, and source URLs."""

    settings = get_settings()
    store = BronzeFilesystemStore(settings.bronze_data_directory)
    if run_id is None:
        manifests = store.list_manifests()
        if not manifests:
            typer.echo("No Bronze runs found.")
            return
        for summary in manifests:
            typer.echo(
                f"{summary.identity.run_id} | {summary.status.value} | "
                f"{summary.completed_work_count}/"
                f"{summary.discovered_work_count} works | "
                f"{len(summary.resources)} resources | "
                f"{len(summary.failures)} failure records"
            )
        return

    selected_manifest = store.find_manifest(run_id)
    if selected_manifest is None:
        typer.echo(f"Bronze run not found: {run_id}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Run: {selected_manifest.identity.run_id}")
    typer.echo(f"Status: {selected_manifest.status.value}")
    typer.echo(f"Started: {selected_manifest.started_at.isoformat()}")
    typer.echo(
        f"Works: {selected_manifest.completed_work_count}/"
        f"{selected_manifest.discovered_work_count}"
    )
    typer.echo(
        f"Canvases: {selected_manifest.canvas_count}; "
        f"annotations: {selected_manifest.annotation_count}; "
        f"missing OCR: {selected_manifest.missing_ocr_page_count}"
    )
    typer.echo(f"Resources: {len(selected_manifest.resources)}")
    for record in selected_manifest.resources:
        typer.echo(
            f"- {record.relative_path} | {record.content_sha256} | {record.source_url}"
        )
    unresolved = [
        failure for failure in selected_manifest.failures if failure.resolved_at is None
    ]
    typer.echo(f"Unresolved failures: {len(unresolved)}")
    for failure in unresolved:
        typer.echo(f"- {failure.source_url} | {failure.message}")


@bronze_app.command("validate")
def validate_bronze(
    run_id: Annotated[
        str | None,
        typer.Option(
            "--run-id",
            help="Validate one run; omit to validate every run.",
        ),
    ] = None,
) -> None:
    """Verify Bronze files, hashes, JSON shapes, and manifest coverage."""

    settings = get_settings()
    store = BronzeFilesystemStore(settings.bronze_data_directory)
    if run_id is None:
        manifest_paths = store.manifest_paths()
    else:
        manifest_paths = tuple(
            path
            for path in store.manifest_paths()
            if path.parent.name.removeprefix("run_id=") == run_id
        )
        if not manifest_paths:
            typer.echo(f"Bronze run not found: {run_id}", err=True)
            raise typer.Exit(code=1)

    if not manifest_paths:
        typer.echo("No Bronze runs found.")
        return

    invalid = False
    for path in manifest_paths:
        try:
            manifest = store.load_manifest_path(path)
        except (OSError, ValueError, BronzeManifestIdentityError) as error:
            invalid = True
            typer.echo(
                f"{path}: invalid manifest ({type(error).__name__}: {error})",
                err=True,
            )
            continue
        report = validate_bronze_run(store, manifest)
        typer.echo(
            f"{report.run_id}: "
            f"{'valid' if report.is_valid else 'invalid'} "
            f"({report.checked_resource_count} resources checked)"
        )
        for issue in report.issues:
            invalid = True
            location = issue.relative_path or "run"
            typer.echo(
                f"- {issue.code} | {location} | {issue.message}",
                err=True,
            )

    if invalid:
        raise typer.Exit(code=1)


def main() -> None:
    """Run the HeritageRAG command-line application."""

    app()
