"""Persistent settings and application logging."""

import logging
import os
import tempfile
from logging.handlers import RotatingFileHandler
from pathlib import Path

from pydantic import ValidationError

from sitepulse.config import MonitoringSettings

CONFIG_PATH = Path("sitepulse.json")
LOGGER_NAME = "sitepulse"

# Track only logging handlers created by SitePulse.
_managed_handlers: list[logging.Handler] = []


class ConfigurationError(Exception):
    """Raised when settings cannot be read, saved, or applied."""


def load_settings(
    path: Path = CONFIG_PATH,
) -> MonitoringSettings:
    """Load validated settings or return defaults."""
    if not path.exists():
        return MonitoringSettings()

    try:
        content = path.read_text(encoding="utf-8")
        return MonitoringSettings.model_validate_json(content)
    except (OSError, ValidationError, ValueError) as exc:
        raise ConfigurationError(f"Could not load valid configuration from {path}") from exc


def save_settings(
    settings: MonitoringSettings,
    path: Path = CONFIG_PATH,
) -> None:
    """Atomically save settings as readable JSON."""
    temporary: Path | None = None

    try:
        path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=".sitepulse-",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(settings.model_dump_json(indent=2))
            stream.write("\n")

        os.replace(temporary, path)

    except OSError as exc:
        raise ConfigurationError("Could not save SitePulse configuration") from exc

    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def configure_logging(
    settings: MonitoringSettings,
) -> logging.Logger:
    """Configure console and rotating-file application logs."""
    logger = logging.getLogger(LOGGER_NAME)

    try:
        settings.log_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)

        file_handler = RotatingFileHandler(
            settings.log_file,
            maxBytes=settings.log_max_bytes,
            backupCount=settings.log_backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)

    except OSError as exc:
        raise ConfigurationError("Could not configure application logging") from exc

    # Remove only handlers previously created by SitePulse.
    for handler in _managed_handlers:
        logger.removeHandler(handler)
        handler.close()

    _managed_handlers.clear()

    # Register and track new SitePulse handlers.
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    _managed_handlers.extend((console_handler, file_handler))

    logger.setLevel(settings.log_level)
    logger.propagate = False

    return logger
