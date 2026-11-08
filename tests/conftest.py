"""Shared test fixtures for SitePulse."""

import logging
from collections.abc import Iterator
from pathlib import Path

import pytest

from sitepulse import cli, runtime
from sitepulse.config import MonitoringSettings


@pytest.fixture(autouse=True)
def isolate_application_logging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    """Keep CLI-generated logs out of real application log files."""
    original_configure_logging = runtime.configure_logging

    def configure_test_logging(
        settings: MonitoringSettings,
    ) -> logging.Logger:
        isolated_settings = settings.model_copy(
            update={"log_file": tmp_path / "_test_logs" / "sitepulse.log"}
        )
        return original_configure_logging(isolated_settings)

    monkeypatch.setattr(
        cli,
        "configure_logging",
        configure_test_logging,
    )

    yield

    # Close only handlers managed by SitePulse.
    logger = logging.getLogger(runtime.LOGGER_NAME)

    for handler in list(runtime._managed_handlers):
        logger.removeHandler(handler)
        handler.close()

    runtime._managed_handlers.clear()
