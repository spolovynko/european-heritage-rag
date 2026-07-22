"""Command-line interface for HeritageRAG."""

from importlib.metadata import version
from typing import Annotated

import typer

from european_heritage_rag.core.config import get_settings
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
app.add_typer(ingest_app, name="ingest")


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


def main() -> None:
    """Run the HeritageRAG command-line application."""

    app()
