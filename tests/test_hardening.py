"""Final M9 tests for safe startup and test log isolation."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from sitepulse.cli import app
from sitepulse.config import MonitoringSettings
from sitepulse.models import CheckStatus, MonitoringResult, Website
from sitepulse.runtime import load_settings
from sitepulse.services.monitor import WebsiteMonitor

runner = CliRunner()


def test_corrupt_config_does_not_block_help_or_version(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Safe commands must remain available with invalid settings."""
    monkeypatch.chdir(tmp_path)

    Path("sitepulse.json").write_text(
        "{broken json",
        encoding="utf-8",
    )

    help_result = runner.invoke(app, ["--help"])
    version_result = runner.invoke(app, ["version"])

    assert help_result.exit_code == 0, help_result.output
    assert version_result.exit_code == 0, version_result.output
    assert "SitePulse" in version_result.output


def test_corrupt_config_produces_friendly_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Database commands must fail safely with invalid settings."""
    monkeypatch.chdir(tmp_path)

    Path("sitepulse.json").write_text(
        "{broken json",
        encoding="utf-8",
    )

    for command in (["list"], ["history"], ["report"]):
        result = runner.invoke(app, command)

        assert result.exit_code == 1
        assert "Error:" in result.output
        assert "Traceback" not in result.output


def test_config_reset_backs_up_corrupted_settings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Recovery must require confirmation and preserve a backup."""
    monkeypatch.chdir(tmp_path)

    original_content = "{broken json"
    config_path = Path("sitepulse.json")
    config_path.write_text(
        original_content,
        encoding="utf-8",
    )

    denied = runner.invoke(app, ["config", "reset"])

    assert denied.exit_code == 2
    assert config_path.read_text(encoding="utf-8") == original_content

    recovered = runner.invoke(
        app,
        ["config", "reset", "--force"],
    )

    assert recovered.exit_code == 0, recovered.output
    assert load_settings().timeout_seconds == 10

    backup = Path("sitepulse.json.bak")
    assert backup.exists()
    assert backup.read_text(encoding="utf-8") == original_content

    listing = runner.invoke(app, ["list"])
    assert listing.exit_code == 0, listing.output


def test_cli_monitoring_logs_are_isolated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CLI tests must not write into the normal log directory."""
    monkeypatch.chdir(tmp_path)

    added = runner.invoke(
        app,
        [
            "add",
            "Example",
            "https://example.com",
        ],
    )
    assert added.exit_code == 0, added.output

    async def fake_check(
        self: WebsiteMonitor,
        websites: list[Website],
    ) -> list[MonitoringResult]:
        return [
            MonitoringResult(
                website_url=website.url,
                status=CheckStatus.UP,
                http_status=200,
            )
            for website in websites
        ]

    monkeypatch.setattr(
        WebsiteMonitor,
        "check_all",
        fake_check,
    )

    checked = runner.invoke(app, ["check", "--id", "1"])
    assert checked.exit_code == 0, checked.output

    isolated_log = tmp_path / "_test_logs" / "sitepulse.log"
    normal_log = tmp_path / "logs" / "sitepulse.log"

    assert isolated_log.exists()
    assert "website_id=1" in isolated_log.read_text(encoding="utf-8")
    assert not normal_log.exists()

    # Check that persistent history still works.
    history = runner.invoke(app, ["history", "--id", "1"])
    assert history.exit_code == 0, history.output
    assert "Example" in history.output


def test_configuration_default_is_still_valid() -> None:
    """The new recovery mechanism must preserve normal defaults."""
    settings = MonitoringSettings()

    assert settings.database_path == Path("sitepulse.db")
    assert settings.interval_seconds == 60
    assert settings.retry_count == 2
