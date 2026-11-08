"""CLI monitoring integration tests."""

from pathlib import Path

from pytest import MonkeyPatch
from typer.testing import CliRunner

from sitepulse.cli import app
from sitepulse.models import (
    CheckStatus,
    FailureCategory,
    MonitoringResult,
    Website,
)
from sitepulse.services.monitor import WebsiteMonitor

runner = CliRunner()


def register(db: Path) -> None:
    result = runner.invoke(
        app,
        [
            "add",
            "Example",
            "https://example.com",
            "--db",
            str(db),
        ],
    )
    assert result.exit_code == 0, result.output


def test_check_without_websites(tmp_path: Path) -> None:
    db = tmp_path / "empty.db"

    result = runner.invoke(app, ["check", "--db", str(db)])

    assert result.exit_code == 0
    assert "No enabled websites" in result.output


def test_check_success(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    db = tmp_path / "success.db"
    register(db)

    async def fake_check(
        self: WebsiteMonitor,
        websites: list[Website],
    ) -> list[MonitoringResult]:
        return [
            MonitoringResult(
                website_url=website.url,
                status=CheckStatus.UP,
                http_status=200,
                response_time_ms=25.5,
            )
            for website in websites
        ]

    monkeypatch.setattr(WebsiteMonitor, "check_all", fake_check)

    result = runner.invoke(app, ["check", "--db", str(db)])

    assert result.exit_code == 0, result.output
    assert "SitePulse Monitoring Dashboard" in result.output
    assert "UP: 1" in result.output
    assert "200" in result.output


def test_check_failure(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    db = tmp_path / "failure.db"
    register(db)

    async def fake_check(
        self: WebsiteMonitor,
        websites: list[Website],
    ) -> list[MonitoringResult]:
        return [
            MonitoringResult(
                website_url=website.url,
                status=CheckStatus.DOWN,
                http_status=503,
                failure_category=FailureCategory.HTTP_STATUS,
                attempts=3,
                response_time_ms=100.0,
            )
            for website in websites
        ]

    monkeypatch.setattr(WebsiteMonitor, "check_all", fake_check)

    result = runner.invoke(app, ["check", "--db", str(db)])

    assert result.exit_code == 0, result.output
    assert "DOWN: 1" in result.output
    assert "503" in result.output


def test_check_unknown_id(tmp_path: Path) -> None:
    db = tmp_path / "unknown.db"

    result = runner.invoke(
        app,
        ["check", "--id", "999", "--db", str(db)],
    )

    assert result.exit_code == 1
    assert "not found" in result.output


def test_disabled_website_is_skipped(
    tmp_path: Path,
) -> None:
    db = tmp_path / "disabled.db"
    register(db)

    disabled = runner.invoke(
        app,
        ["disable", "1", "--db", str(db)],
    )
    assert disabled.exit_code == 0

    result = runner.invoke(app, ["check", "--db", str(db)])

    assert result.exit_code == 0
    assert "No enabled websites" in result.output


def test_monitor_limited_rounds(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    db = tmp_path / "monitor.db"
    register(db)
    calls = 0

    async def fake_check(
        self: WebsiteMonitor,
        websites: list[Website],
    ) -> list[MonitoringResult]:
        nonlocal calls
        calls += 1

        return [
            MonitoringResult(
                website_url=website.url,
                status=CheckStatus.UP,
                http_status=200,
            )
            for website in websites
        ]

    monkeypatch.setattr(WebsiteMonitor, "check_all", fake_check)

    result = runner.invoke(
        app,
        [
            "monitor",
            "--count",
            "2",
            "--interval",
            "0.01",
            "--db",
            str(db),
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls == 2
    assert "Monitoring round 2" in result.output
    assert "Monitoring finished" in result.output
