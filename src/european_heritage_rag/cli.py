"""Command-line interface for HeritageRAG."""

from importlib.metadata import version

import typer

_DISTRIBUTION_NAME = "european-heritage-rag"

app = typer.Typer(
    name="european-heritage-rag",
    help="Operate and inspect the HeritageRAG application.",
    no_args_is_help=True,
)


@app.callback()
def cli() -> None:
    """Provide HeritageRAG command-line operations."""


@app.command("version")
def show_version() -> None:
    """Print the installed HeritageRAG version."""

    typer.echo(version(_DISTRIBUTION_NAME))


def main() -> None:
    """Run the HeritageRAG command-line application."""

    app()
