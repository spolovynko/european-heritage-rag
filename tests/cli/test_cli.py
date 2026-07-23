"""Tests for the HeritageRAG command-line interface."""

from importlib.metadata import version
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from european_heritage_rag.cli import app
from european_heritage_rag.core.config import AppSettings
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
    assert "bronze" in result.output
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


def test_bronze_inspect_reports_empty_store(tmp_path: Path) -> None:
    """Inspection should not invent runs before the first acquisition."""

    settings = AppSettings(
        _env_file=None,
        bronze_data_directory=tmp_path / "bronze",
    )
    with patch(
        "european_heritage_rag.cli.get_settings",
        return_value=settings,
    ):
        result = runner.invoke(app, ["bronze", "inspect"])

    assert result.exit_code == 0
    assert "No Bronze runs found." in result.output


def test_bronze_validate_rejects_unknown_run(tmp_path: Path) -> None:
    """A requested run ID must exist before it can be validated."""

    settings = AppSettings(
        _env_file=None,
        bronze_data_directory=tmp_path / "bronze",
    )
    with patch(
        "european_heritage_rag.cli.get_settings",
        return_value=settings,
    ):
        result = runner.invoke(
            app,
            ["bronze", "validate", "--run-id", "missing"],
        )

    assert result.exit_code == 1
    assert "Bronze run not found: missing" in result.output


def test_bronze_validate_reports_invalid_manifest(tmp_path: Path) -> None:
    """Validation should report corrupt ledgers without a Python traceback."""

    settings = AppSettings(
        _env_file=None,
        bronze_data_directory=tmp_path / "bronze",
    )
    manifest_path = (
        settings.bronze_data_directory
        / "wellcome"
        / "ingestion_date=2026-07-23"
        / "run_id=broken-run"
        / "run-manifest.json"
    )
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text('{"not":"a manifest"}', encoding="utf-8")

    with patch(
        "european_heritage_rag.cli.get_settings",
        return_value=settings,
    ):
        result = runner.invoke(app, ["bronze", "validate"])

    assert result.exit_code == 1
    assert "invalid manifest" in result.output
    assert "Traceback" not in result.output
