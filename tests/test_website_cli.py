"""Tests for website management CLI commands."""

from pathlib import Path

from typer.testing import CliRunner

from sitepulse.cli import app

runner = CliRunner()


def test_add_and_list(tmp_path: Path) -> None:
    db = str(tmp_path / "cli.db")

    added = runner.invoke(
        app,
        ["add", "Google", "https://google.com", "--db", db],
    )

    assert added.exit_code == 0, added.output
    assert "Added" in added.output

    listed = runner.invoke(app, ["list", "--db", db])

    assert listed.exit_code == 0, listed.output
    assert "Google" in listed.output
    assert "https://google.com" in listed.output


def test_duplicate_rejected(tmp_path: Path) -> None:
    db = str(tmp_path / "cli.db")

    first = runner.invoke(
        app,
        ["add", "First", "https://example.com", "--db", db],
    )

    second = runner.invoke(
        app,
        ["add", "Second", "https://EXAMPLE.COM/", "--db", db],
    )

    assert first.exit_code == 0
    assert second.exit_code == 1
    assert "already registered" in second.output


def test_disable_enable_remove(tmp_path: Path) -> None:
    db = str(tmp_path / "cli.db")

    added = runner.invoke(
        app,
        ["add", "Example", "https://example.com", "--db", db],
    )
    assert added.exit_code == 0, added.output

    disabled = runner.invoke(app, ["disable", "1", "--db", db])
    assert disabled.exit_code == 0, disabled.output

    enabled = runner.invoke(app, ["enable", "1", "--db", db])
    assert enabled.exit_code == 0, enabled.output

    removed = runner.invoke(app, ["remove", "1", "--db", db])
    assert removed.exit_code == 0, removed.output

    listed = runner.invoke(app, ["list", "--db", db])
    assert "No websites registered" in listed.output


def test_invalid_url(tmp_path: Path) -> None:
    db = str(tmp_path / "cli.db")

    result = runner.invoke(
        app,
        ["add", "Bad", "not-a-url", "--db", db],
    )

    assert result.exit_code == 1
    assert "Error:" in result.output


def test_unknown_website(tmp_path: Path) -> None:
    db = str(tmp_path / "cli.db")

    result = runner.invoke(app, ["remove", "999", "--db", db])

    assert result.exit_code == 1
    assert "not found" in result.output
