"""Tests for the HeritageRAG command-line interface."""

from importlib.metadata import version

from typer.testing import CliRunner

from european_heritage_rag.cli import app

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
    assert "version" in result.output
