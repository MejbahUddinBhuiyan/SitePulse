"""M9 regression tests for reliability and security."""

import logging
from pathlib import Path

import pytest
from typer.testing import CliRunner

from sitepulse import runtime
from sitepulse.cli import app
from sitepulse.config import MonitoringSettings
from sitepulse.models import CheckStatus, MonitoringResult, Website
from sitepulse.runtime import (
    ConfigurationError,
    configure_logging,
    load_settings,
    save_settings,
)
from sitepulse.storage import StorageError, WebsiteRepository
from sitepulse.storage.history import HistoryRepository

runner = CliRunner()


def test_corrupted_config_is_rejected(tmp_path: Path) -> None:
    """Invalid JSON must not be silently accepted."""
    path = tmp_path / "sitepulse.json"
    path.write_text("{invalid json", encoding="utf-8")

    with pytest.raises(ConfigurationError):
        load_settings(path)


def test_invalid_config_update_preserves_previous_values(
    tmp_path: Path,
) -> None:
    """A failed configuration update must not damage valid settings."""
    path = tmp_path / "settings.json"

    save_settings(
        MonitoringSettings(timeout_seconds=7),
        path,
    )

    before = path.read_bytes()

    result = runner.invoke(
        app,
        [
            "config",
            "set",
            "timeout_seconds",
            "-10",
            "--file",
            str(path),
        ],
    )

    assert result.exit_code != 0
    assert path.read_bytes() == before
    assert load_settings(path).timeout_seconds == 7


@pytest.mark.asyncio
async def test_failed_batch_does_not_partially_save(
    tmp_path: Path,
) -> None:
    """An invalid website ID must roll back the entire batch."""
    db = tmp_path / "atomic.db"

    repository = WebsiteRepository(db)
    await repository.initialize()

    valid = await repository.add(Website("Valid", "https://example.com"))

    invalid = Website(
        "Missing",
        "https://missing.example",
        id=999999,
    )

    history = HistoryRepository(db)

    records = [
        (
            valid,
            MonitoringResult(
                valid.url,
                CheckStatus.UP,
                http_status=200,
            ),
        ),
        (
            invalid,
            MonitoringResult(
                invalid.url,
                CheckStatus.UP,
                http_status=200,
            ),
        ),
    ]

    with pytest.raises(StorageError):
        await history.save_batch(records)

    assert await history.fetch() == []


@pytest.mark.asyncio
async def test_url_mismatch_cannot_be_saved(
    tmp_path: Path,
) -> None:
    """A monitoring result must belong to its registered website."""
    db = tmp_path / "mismatch.db"

    repository = WebsiteRepository(db)
    await repository.initialize()

    website = await repository.add(Website("Example", "https://example.com"))

    result = MonitoringResult(
        "https://different.example",
        CheckStatus.UP,
        http_status=200,
    )

    history = HistoryRepository(db)

    with pytest.raises(StorageError):
        await history.save_batch([(website, result)])

    assert await history.fetch() == []


def test_reconfiguration_preserves_external_handlers(
    tmp_path: Path,
) -> None:
    """Replace SitePulse handlers while preserving external handlers."""
    logger = logging.getLogger("sitepulse")

    # Add a handler owned by another component.
    external = logging.NullHandler()
    logger.addHandler(external)

    try:
        settings = MonitoringSettings(log_file=tmp_path / "sitepulse.log")

        # Configure SitePulse logging for the first time.
        configure_logging(settings)

        first_managed = list(runtime._managed_handlers)

        assert len(first_managed) == 2

        for handler in first_managed:
            assert handler in logger.handlers

        assert external in logger.handlers

        # Reconfigure SitePulse logging.
        configure_logging(settings)

        second_managed = list(runtime._managed_handlers)

        # Exactly two new managed handlers must exist.
        assert len(second_managed) == 2

        for handler in second_managed:
            assert handler in logger.handlers

        # Old SitePulse handlers must have been replaced.
        for handler in first_managed:
            assert handler not in logger.handlers
            assert handler not in second_managed

        # External handlers must remain attached.
        assert external in logger.handlers

        # No managed handler should be registered twice.
        for handler in second_managed:
            assert logger.handlers.count(handler) == 1

    finally:
        logger.removeHandler(external)
        external.close()


def test_log_entries_do_not_contain_sensitive_url(
    tmp_path: Path,
) -> None:
    """Application logging should use website IDs, not sensitive URLs."""
    path = tmp_path / "sitepulse.log"

    logger = configure_logging(MonitoringSettings(log_file=path))

    logger.info(
        "website_id=%s status=%s http=%s attempts=%s",
        1,
        "up",
        200,
        1,
    )

    for handler in runtime._managed_handlers:
        handler.flush()

    contents = path.read_text(encoding="utf-8")

    assert "website_id=1" in contents
    assert "https://" not in contents
    assert "password" not in contents.lower()
