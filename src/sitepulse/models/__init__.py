"""Typed objects used by SitePulse."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from urllib.parse import urlsplit


class WebsiteValidationError(ValueError):
    """Raised when a website name or URL is invalid."""


def validate_website_url(url: str) -> str:
    """Validate an HTTP(S) website URL."""
    cleaned = url.strip()

    if not cleaned or any(char.isspace() for char in cleaned):
        raise WebsiteValidationError("URL cannot be empty or contain whitespace")

    try:
        parts = urlsplit(cleaned)

        if parts.scheme.lower() not in {"http", "https"}:
            raise WebsiteValidationError("URL must start with http:// or https://")

        if not parts.hostname:
            raise WebsiteValidationError("URL must include a hostname")

        if parts.username is not None or parts.password is not None:
            raise WebsiteValidationError("Credentials are not allowed inside website URLs")

        _ = parts.port

    except ValueError as exc:
        raise WebsiteValidationError("URL contains an invalid hostname or port") from exc

    return cleaned


class CheckStatus(StrEnum):
    UP = "up"
    DOWN = "down"


class FailureCategory(StrEnum):
    DNS = "dns"
    CONNECTION = "connection"
    TIMEOUT = "timeout"
    SSL = "ssl"
    HTTP_STATUS = "http_status"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class Website:
    name: str
    url: str
    enabled: bool = True
    id: int | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise WebsiteValidationError("Website name cannot be empty")

        if self.id is not None and self.id <= 0:
            raise WebsiteValidationError("Website ID must be positive")

        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "url", validate_website_url(self.url))


@dataclass(frozen=True, slots=True)
class MonitoringResult:
    website_url: str
    status: CheckStatus
    checked_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    http_status: int | None = None
    response_time_ms: float | None = None
    failure_category: FailureCategory | None = None
    error_message: str | None = None
    attempts: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "website_url",
            validate_website_url(self.website_url),
        )

        if self.checked_at.tzinfo is None or self.checked_at.utcoffset() is None:
            raise ValueError("checked_at must include a timezone")

        if self.http_status is not None and not 100 <= self.http_status <= 599:
            raise ValueError("HTTP status must be between 100 and 599")

        if self.response_time_ms is not None and self.response_time_ms < 0:
            raise ValueError("Response time cannot be negative")

        if self.attempts < 1:
            raise ValueError("Attempts must be at least 1")

        if self.status == CheckStatus.UP and self.failure_category is not None:
            raise ValueError("Successful checks cannot have a failure category")

        if self.status == CheckStatus.DOWN and self.failure_category is None:
            raise ValueError("Failed checks must include a failure category")
