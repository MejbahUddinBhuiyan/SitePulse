"""Asynchronous HTTP checks with bounded concurrency."""

import asyncio
import socket
from datetime import UTC, datetime
from time import perf_counter

import aiohttp

from sitepulse.config import MonitoringSettings
from sitepulse.models import (
    CheckStatus,
    FailureCategory,
    MonitoringResult,
    Website,
)


class WebsiteMonitor:
    """Run one batch of HTTP checks; no retry or persistence yet."""

    def __init__(self, settings: MonitoringSettings) -> None:
        self.settings = settings

    async def check_one(
        self,
        website: Website,
        session: aiohttp.ClientSession,
        semaphore: asyncio.Semaphore,
    ) -> MonitoringResult:
        """Check one website and classify network failures."""
        async with semaphore:
            checked_at = datetime.now(UTC)
            started = perf_counter()

            status_code: int | None = None
            category: FailureCategory | None = None
            message: str | None = None

            try:
                async with session.get(website.url) as response:
                    status_code = response.status

                    if not (
                        self.settings.success_status_min
                        <= status_code
                        <= self.settings.success_status_max
                    ):
                        category = FailureCategory.HTTP_STATUS
                        message = f"HTTP {status_code}"

            except asyncio.CancelledError:
                raise

            except TimeoutError:
                category = FailureCategory.TIMEOUT
                message = "Request timed out"

            except (
                aiohttp.ClientConnectorCertificateError,
                aiohttp.ClientSSLError,
            ):
                category = FailureCategory.SSL
                message = "TLS/SSL verification failed"

            except aiohttp.ClientConnectorError as exc:
                category = (
                    FailureCategory.DNS
                    if isinstance(exc.os_error, socket.gaierror)
                    else FailureCategory.CONNECTION
                )
                message = (
                    "DNS lookup failed" if category == FailureCategory.DNS else "Connection failed"
                )

            except aiohttp.ClientError:
                category = FailureCategory.CONNECTION
                message = "HTTP connection or protocol error"

            duration_ms = (perf_counter() - started) * 1000

            return MonitoringResult(
                website_url=website.url,
                status=(CheckStatus.DOWN if category is not None else CheckStatus.UP),
                checked_at=checked_at,
                http_status=status_code,
                response_time_ms=duration_ms,
                failure_category=category,
                error_message=message,
            )

    async def check_all(
        self,
        websites: list[Website],
    ) -> list[MonitoringResult]:
        """Check enabled websites concurrently in input order."""
        enabled = [website for website in websites if website.enabled]

        if not enabled:
            return []

        semaphore = asyncio.Semaphore(self.settings.max_concurrency)

        timeout = aiohttp.ClientTimeout(total=self.settings.timeout_seconds)

        async with aiohttp.ClientSession(
            timeout=timeout,
            trust_env=False,
        ) as session:
            return list(
                await asyncio.gather(
                    *(self.check_one(site, session, semaphore) for site in enabled)
                )
            )
