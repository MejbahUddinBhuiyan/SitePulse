"""Tests for SitePulse configuration validation."""

import pytest
from pydantic import ValidationError

from sitepulse.config import MonitoringSettings


def test_defaults() -> None:
    settings = MonitoringSettings()

    assert settings.interval_seconds == 60
    assert settings.max_concurrency == 10
    assert settings.success_status_min == 200


@pytest.mark.parametrize(
    "overrides",
    [
        {"interval_seconds": 0},
        {"timeout_seconds": -1},
        {"max_concurrency": 0},
        {"retry_count": -1},
        {
            "success_status_min": 500,
            "success_status_max": 200,
        },
        {
            "retry_base_delay_seconds": 20,
            "retry_max_delay_seconds": 5,
        },
        {"database_path": ""},
        {"output_format": "xml"},
        {"unknown": True},
    ],
)
def test_invalid_settings(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        MonitoringSettings.model_validate(overrides)


def test_custom_settings() -> None:
    settings = MonitoringSettings(
        max_concurrency=3,
        timeout_seconds=2.5,
    )

    assert settings.max_concurrency == 3
    assert settings.timeout_seconds == 2.5
