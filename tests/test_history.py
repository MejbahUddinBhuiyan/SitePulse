"""M7 history persistence and reporting tests."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from typer.testing import CliRunner

from sitepulse.cli import app
from sitepulse.models import CheckStatus, FailureCategory, MonitoringResult, Website
from sitepulse.reports import CheckSummary, export_summaries, summarize
from sitepulse.services.monitor import WebsiteMonitor
from sitepulse.storage import WebsiteRepository
from sitepulse.storage.history import HistoryRepository

runner = CliRunner()


@pytest.mark.asyncio
async def test_save_and_load(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    repo = WebsiteRepository(db)
    await repo.initialize()

    website = await repo.add(Website("Example", "https://example.com"))

    history = HistoryRepository(db)
    result = MonitoringResult(
        website.url,
        CheckStatus.UP,
        http_status=200,
        response_time_ms=50.0,
    )

    await history.save_batch([(website, result)])
    found = await HistoryRepository(db).fetch()

    assert len(found) == 1
    assert found[0].website_name == "Example"
    assert found[0].result.http_status == 200


@pytest.mark.asyncio
async def test_window_and_website_filter(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    repo = WebsiteRepository(db)
    await repo.initialize()

    one = await repo.add(Website("One", "https://one.test"))
    two = await repo.add(Website("Two", "https://two.test"))

    now = datetime.now(UTC)
    history = HistoryRepository(db)

    await history.save_batch(
        [
            (
                one,
                MonitoringResult(
                    one.url,
                    CheckStatus.UP,
                    checked_at=now,
                ),
            ),
            (
                one,
                MonitoringResult(
                    one.url,
                    CheckStatus.DOWN,
                    checked_at=now - timedelta(days=2),
                    failure_category=FailureCategory.TIMEOUT,
                ),
            ),
            (
                two,
                MonitoringResult(
                    two.url,
                    CheckStatus.UP,
                    checked_at=now,
                ),
            ),
        ]
    )

    filtered = await history.fetch(
        website_id=one.id,
        since=now - timedelta(hours=1),
    )

    assert len(filtered) == 1
    assert filtered[0].result.status == CheckStatus.UP
    assert len(await history.fetch(limit=2)) == 2


@pytest.mark.asyncio
async def test_summary_calculations(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    repo = WebsiteRepository(db)
    await repo.initialize()

    website = await repo.add(Website("A", "https://a.test"))

    history = HistoryRepository(db)

    await history.save_batch(
        [
            (
                website,
                MonitoringResult(
                    website.url,
                    CheckStatus.UP,
                    response_time_ms=10,
                ),
            ),
            (
                website,
                MonitoringResult(
                    website.url,
                    CheckStatus.DOWN,
                    response_time_ms=30,
                    failure_category=FailureCategory.TIMEOUT,
                ),
            ),
        ]
    )

    summary = summarize(await history.fetch())[0]

    assert (
        summary.checks,
        summary.successful,
        summary.failed,
    ) == (2, 1, 1)

    assert summary.observed_success_percent == 50
    assert (
        summary.average_ms,
        summary.minimum_ms,
        summary.maximum_ms,
    ) == (20, 10, 30)


def test_json_and_csv_export(tmp_path: Path) -> None:
    summary = CheckSummary(1, "=TEST", 2, 1, 1, 50.0, 20.0, 10.0, 30.0)

    json_path = tmp_path / "report.json"
    csv_path = tmp_path / "report.csv"

    export_summaries(json_path, [summary], "json")
    export_summaries(csv_path, [summary], "csv")

    assert json.loads(json_path.read_text(encoding="utf-8"))[0]["checks"] == 2
    assert "'=TEST" in csv_path.read_text(encoding="utf-8-sig")


def test_report_cli_no_history(tmp_path: Path) -> None:
    db = tmp_path / "report.db"

    result = runner.invoke(app, ["report", "--db", str(db)])

    assert result.exit_code == 0, result.output
    assert "No checks recorded" in result.output


def test_history_cli_no_history(tmp_path: Path) -> None:
    db = tmp_path / "history.db"

    result = runner.invoke(app, ["history", "--db", str(db)])

    assert result.exit_code == 0, result.output
    assert "No checks recorded" in result.output


def test_export_cli_requires_output(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "report",
            "--format",
            "csv",
            "--db",
            str(tmp_path / "db"),
        ],
    )

    assert result.exit_code == 2
    assert "--output is required" in result.output


def test_check_cli_persists_results(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = tmp_path / "checks.db"

    added = runner.invoke(
        app,
        [
            "add",
            "Example",
            "https://example.com",
            "--db",
            str(db),
        ],
    )
    assert added.exit_code == 0, added.output

    async def fake_check(
        self: WebsiteMonitor,
        websites: list[Website],
    ) -> list[MonitoringResult]:
        return [
            MonitoringResult(
                website.url,
                CheckStatus.UP,
                http_status=200,
            )
            for website in websites
        ]

    monkeypatch.setattr(WebsiteMonitor, "check_all", fake_check)

    checked = runner.invoke(app, ["check", "--db", str(db)])
    assert checked.exit_code == 0, checked.output

    history = runner.invoke(app, ["history", "--db", str(db)])
    assert history.exit_code == 0, history.output
    assert "Example" in history.output

    report = runner.invoke(app, ["report", "--db", str(db)])
    assert report.exit_code == 0, report.output
    assert "100.00%" in report.output


def test_export_cli_json(tmp_path: Path) -> None:
    db = tmp_path / "db.sqlite"
    target = tmp_path / "exports" / "results.json"

    result = runner.invoke(
        app,
        [
            "report",
            "--format",
            "json",
            "--output",
            str(target),
            "--db",
            str(db),
        ],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(target.read_text(encoding="utf-8")) == []


@pytest.mark.asyncio
async def test_history_cascades_on_website_deletion(
    tmp_path: Path,
) -> None:
    db = tmp_path / "db.sqlite"
    repo = WebsiteRepository(db)
    await repo.initialize()

    website = await repo.add(Website("A", "https://a.test"))
    assert website.id is not None

    history = HistoryRepository(db)

    await history.save_batch(
        [
            (
                website,
                MonitoringResult(
                    website.url,
                    CheckStatus.UP,
                ),
            )
        ]
    )

    await repo.remove(website.id)

    assert await history.fetch() == []
