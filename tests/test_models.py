"""Tests for SitePulse domain models."""

from datetime import UTC, datetime

import pytest

from sitepulse.models import (
    CheckStatus,
    FailureCategory,
    MonitoringResult,
    Website,
    WebsiteValidationError,
    validate_website_url,
)


def test_valid_website() -> None:
    website = Website(
        name=" Example ",
        url=" https://example.com/path ",
    )

    assert website.name == "Example"
    assert website.url == "https://example.com/path"
    assert website.enabled is True


@pytest.mark.parametrize(
    "url",
    [
        "",
        "example.com",
        "ftp://example.com",
        "https://",
        "https://a:bad",
        "https://user:password@example.com",
        "https://example.com/a b",
    ],
)
def test_invalid_urls(url: str) -> None:
    with pytest.raises(WebsiteValidationError):
        validate_website_url(url)


def test_invalid_website_name() -> None:
    with pytest.raises(WebsiteValidationError):
        Website(name="  ", url="https://example.com")


def test_valid_success_result() -> None:
    result = MonitoringResult(
        website_url="https://example.com",
        status=CheckStatus.UP,
        http_status=200,
        response_time_ms=12.5,
    )

    assert result.attempts == 1
    assert result.checked_at.tzinfo is not None


def test_failure_requires_category() -> None:
    with pytest.raises(ValueError, match="failure category"):
        MonitoringResult(
            website_url="https://example.com",
            status=CheckStatus.DOWN,
        )


def test_naive_timestamp_rejected() -> None:
    with pytest.raises(ValueError, match="timezone"):
        MonitoringResult(
            website_url="https://example.com",
            status=CheckStatus.DOWN,
            failure_category=FailureCategory.TIMEOUT,
            checked_at=datetime(2026, 1, 1),
        )


def test_aware_timestamp_accepted() -> None:
    value = datetime(2026, 1, 1, tzinfo=UTC)

    result = MonitoringResult(
        website_url="https://example.com",
        status=CheckStatus.DOWN,
        failure_category=FailureCategory.TIMEOUT,
        checked_at=value,
    )

    assert result.checked_at == value
