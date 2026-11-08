"""Smoke tests for the Milestone 1 CLI."""

from typer.testing import CliRunner

from sitepulse import __version__
from sitepulse.cli import app

runner = CliRunner()


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert f"SitePulse {__version__}" in result.stdout


def test_doctor_command() -> None:
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "SitePulse Environment" in result.stdout
    assert "PASS" in result.stdout


def test_help_lists_initial_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "version" in result.stdout
    assert "doctor" in result.stdout
