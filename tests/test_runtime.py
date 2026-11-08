"""Tests for configuration persistence and application logging."""

from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from sitepulse.cli import app
from sitepulse.config import MonitoringSettings
from sitepulse.runtime import (
    ConfigurationError,
    configure_logging,
    load_settings,
    save_settings,
)

runner = CliRunner()


def test_default_settings(tmp_path: Path) -> None:
    settings = load_settings(tmp_path / "missing.json")

    assert settings.timeout_seconds == 10
    assert settings.retry_count == 2
    assert settings.log_level == "INFO"


def test_settings_persist(tmp_path: Path) -> None:
    path = tmp_path / "sitepulse.json"

    settings = MonitoringSettings(
        timeout_seconds=5,
        max_concurrency=20,
        log_level="DEBUG",
    )

    save_settings(settings, path)
    loaded = load_settings(path)

    assert loaded == settings


def test_invalid_configuration_rejected(
    tmp_path: Path,
) -> None:
    path = tmp_path / "invalid.json"
    path.write_text(
        '{"max_concurrency": -2}',
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError):
        load_settings(path)


def test_invalid_log_settings() -> None:
    with pytest.raises(ValidationError):
        MonitoringSettings(log_max_bytes=10)

    with pytest.raises(ValidationError):
        MonitoringSettings(log_backup_count=-1)


def test_config_cli_set_and_show(tmp_path: Path) -> None:
    config_file = tmp_path / "settings.json"

    result = runner.invoke(
        app,
        [
            "config",
            "set",
            "timeout_seconds",
            "5",
            "--file",
            str(config_file),
        ],
    )

    assert result.exit_code == 0, result.output
    assert load_settings(config_file).timeout_seconds == 5

    shown = runner.invoke(
        app,
        [
            "config",
            "show",
            "--file",
            str(config_file),
        ],
    )

    assert shown.exit_code == 0, shown.output
    assert '"timeout_seconds": 5' in shown.output


def test_invalid_cli_setting_does_not_save(
    tmp_path: Path,
) -> None:
    config_file = tmp_path / "settings.json"

    result = runner.invoke(
        app,
        [
            "config",
            "set",
            "max_concurrency",
            "-5",
            "--file",
            str(config_file),
        ],
    )

    assert result.exit_code != 0
    assert not config_file.exists()


def test_rotating_log_file(tmp_path: Path) -> None:
    log_file = tmp_path / "logs" / "sitepulse.log"

    settings = MonitoringSettings(
        log_file=log_file,
        log_level="DEBUG",
        log_max_bytes=1024,
        log_backup_count=2,
    )

    logger = configure_logging(settings)

    for index in range(100):
        logger.info("website_id=1 check=%s status=up", index)

    for handler in list(logger.handlers):
        if getattr(handler, "_sitepulse_managed", False):
            handler.flush()

    assert log_file.exists()
    assert (tmp_path / "logs" / "sitepulse.log.1").exists()

    contents = log_file.read_text(encoding="utf-8")
    assert "website_id=1" in contents

    # Clean up the test's logging handlers.
    for handler in list(logger.handlers):
        if getattr(handler, "_sitepulse_managed", False):
            logger.removeHandler(handler)
            handler.close()


def test_log_does_not_require_website_url(
    tmp_path: Path,
) -> None:
    log_file = tmp_path / "sitepulse.log"

    logger = configure_logging(MonitoringSettings(log_file=log_file))

    logger.info(
        "website_id=%s status=%s",
        1,
        "up",
    )

    for handler in list(logger.handlers):
        if getattr(handler, "_sitepulse_managed", False):
            handler.flush()

    contents = log_file.read_text(encoding="utf-8")

    assert "website_id=1" in contents
    assert "https://" not in contents

    for handler in list(logger.handlers):
        if getattr(handler, "_sitepulse_managed", False):
            logger.removeHandler(handler)
            handler.close()
