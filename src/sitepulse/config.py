"""Validated monitoring settings for SitePulse."""

from pathlib import Path
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class MonitoringSettings(BaseModel):
    """Configuration for the monitoring engine."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    interval_seconds: float = Field(default=60, gt=0)
    timeout_seconds: float = Field(default=10, gt=0)
    max_concurrency: int = Field(default=10, ge=1, le=1000)

    retry_count: int = Field(default=2, ge=0, le=10)
    retry_base_delay_seconds: float = Field(default=0.5, gt=0)
    retry_max_delay_seconds: float = Field(default=10, gt=0)
    retry_jitter: bool = True

    success_status_min: int = Field(default=200, ge=100, le=599)
    success_status_max: int = Field(default=399, ge=100, le=599)

    database_path: Path = Path("sitepulse.db")
    output_format: Literal["table", "json"] = "table"

    @field_validator("database_path")
    @classmethod
    def database_path_not_empty(cls, value: Path) -> Path:
        if not str(value).strip() or str(value) == ".":
            raise ValueError("database_path must point to a file")
        return value

    @model_validator(mode="after")
    def validate_ranges(self) -> "MonitoringSettings":
        if self.success_status_min > self.success_status_max:
            raise ValueError("success_status_min must not exceed success_status_max")

        if self.retry_base_delay_seconds > self.retry_max_delay_seconds:
            raise ValueError("Retry base delay must not exceed maximum retry delay")

        return self
