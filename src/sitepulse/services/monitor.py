"""Asynchronous website checks with selective retry and graceful cancellation."""

import asyncio
import random
import socket
from datetime import UTC, datetime
from time import perf_counter

import aiohttp

from sitepulse.config import MonitoringSettings
from sitepulse.models import CheckStatus, FailureCategory, MonitoringResult, Website


class WebsiteMonitor:
    """Check enabled websites concurrently using bounded HTTP requests."""

    RETRYABLE_HTTP_STATUSES = frozenset({408, 429, 500, 502, 503, 504})
    RETRYABLE_FAILURES = frozenset({FailureCategory.CONNECTION, FailureCategory.TIMEOUT})

    def __init__(self, settings: MonitoringSettings) -> None:
        self.settings = settings

    def _retry_delay(self, retry_number: int) -> float:
        """Calculate bounded exponential backoff."""
        delay: float = min(
            self.settings.retry_base_delay_seconds * (2 ** (retry_number - 1)),
            self.settings.retry_max_delay_seconds,
        )

        if self.settings.retry_jitter:
            return float(random.uniform(0.0, delay))

        return delay

    def _should_retry(self, result: MonitoringResult) -> bool:
        """Retry only known temporary HTTP or transport failures."""
        if result.failure_category == FailureCategory.HTTP_STATUS:
            return result.http_status in self.RETRYABLE_HTTP_STATUSES
        return result.failure_category in self.RETRYABLE_FAILURES

    async def _request_once(
        self,
        website: Website,
        session: aiohttp.ClientSession,
        semaphore: asyncio.Semaphore,
    ) -> tuple[int | None, FailureCategory | None, str | None]:
        """Perform one HTTP request while holding a concurrency slot."""
        async with semaphore:
            try:
                async with session.get(website.url) as response:
                    code = response.status
                    if self.settings.success_status_min <= code <= self.settings.success_status_max:
                        return code, None, None
                    return code, FailureCategory.HTTP_STATUS, f"HTTP {code}"

            except asyncio.CancelledError:
                raise
            except TimeoutError:
                return None, FailureCategory.TIMEOUT, "Request timed out"
            except (aiohttp.ClientConnectorCertificateError, aiohttp.ClientSSLError):
                return None, FailureCategory.SSL, "TLS/SSL verification failed"
            except aiohttp.ClientConnectorError as exc:
                if isinstance(exc.os_error, socket.gaierror):
                    return None, FailureCategory.DNS, "DNS lookup failed"
                return None, FailureCategory.CONNECTION, "Connection failed"
            except aiohttp.ClientError:
                return None, FailureCategory.CONNECTION, "HTTP connection or protocol error"

    async def check_one(
        self,
        website: Website,
        session: aiohttp.ClientSession,
        semaphore: asyncio.Semaphore,
    ) -> MonitoringResult:
        """Check one website, retrying eligible errors up to retry_count times."""
        checked_at = datetime.now(UTC)
        started = perf_counter()
        max_attempts = self.settings.retry_count + 1

        for attempt in range(1, max_attempts + 1):
            code, category, message = await self._request_once(website, session, semaphore)

            result = MonitoringResult(
                website_url=website.url,
                status=CheckStatus.DOWN if category is not None else CheckStatus.UP,
                checked_at=checked_at,
                http_status=code,
                response_time_ms=(perf_counter() - started) * 1000,
                failure_category=category,
                error_message=message,
                attempts=attempt,
            )

            if category is None or attempt == max_attempts or not self._should_retry(result):
                return result

            # Do not occupy a semaphore slot while waiting to retry.
            await asyncio.sleep(self._retry_delay(attempt))

        raise RuntimeError("Unreachable: at least one request attempt is required")

    async def check_all(self, websites: list[Website]) -> list[MonitoringResult]:
        """Run one concurrent batch, skipping disabled websites."""
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
