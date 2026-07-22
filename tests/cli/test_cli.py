"""Tests for the HeritageRAG command-line interface."""

from importlib.metadata import version
from unittest.mock import patch

from typer.testing import CliRunner

from european_heritage_rag.cli import app
from european_heritage_rag.sources.wellcome.ingestion import IngestionStatus

_DISTRIBUTION_NAME = "european-heritage-rag"

runner = CliRunner()


def test_version_command_prints_installed_version() -> None:
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.output.strip() == version(_DISTRIBUTION_NAME)


def test_help_lists_available_commands() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Operate and inspect the HeritageRAG application." in result.output
    assert "ingest" in result.output
    assert "version" in result.output


def test_wellcome_ingestion_command_forwards_validated_options() -> None:
    status = IngestionStatus(
        status="completed",
        run_id="test-run",
        requested_limit=2,
        query="cholera",
        works_discovered=2,
        dry_run=True,
    )

    with patch(
        "european_heritage_rag.cli.run_wellcome_ingestion",
        return_value=status,
    ) as run_mock:
        result = runner.invoke(
            app,
            [
                "ingest",
                "wellcome",
                "--limit",
                "2",
                "--query",
                "cholera",
                "--dry-run",
            ],
        )

    assert result.exit_code == 0
    assert "Run: test-run" in result.output
    assert "Status: completed" in result.output
    assert "Works: 0/2" in result.output
    run_mock.assert_called_once()
    assert run_mock.call_args.kwargs == {
        "limit": 2,
        "query": "cholera",
        "language": "eng",
        "resume": False,
        "dry_run": True,
    }


def test_wellcome_ingestion_rejects_resume_with_dry_run() -> None:
    with patch("european_heritage_rag.cli.run_wellcome_ingestion") as run_mock:
        result = runner.invoke(
            app,
            ["ingest", "wellcome", "--resume", "--dry-run"],
        )

    assert result.exit_code == 2
    assert "cannot be used together" in result.output
    run_mock.assert_not_called()


def test_wellcome_ingestion_rejects_unsupported_language() -> None:
    with patch("european_heritage_rag.cli.run_wellcome_ingestion") as run_mock:
        result = runner.invoke(
            app,
            ["ingest", "wellcome", "--language", "fra"],
        )

    assert result.exit_code == 2
    assert "must be eng" in result.output
    run_mock.assert_not_called()
