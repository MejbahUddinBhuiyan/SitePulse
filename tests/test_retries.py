"""Retry and cancellation tests using a local HTTP server."""

import asyncio
import socket
from collections.abc import Awaitable, Callable
from unittest.mock import patch

import aiohttp
import pytest

from sitepulse.config import MonitoringSettings
from sitepulse.models import CheckStatus, FailureCategory, Website
from sitepulse.services.monitor import WebsiteMonitor


async def start_server(
    handler: Callable[
        [asyncio.StreamReader, asyncio.StreamWriter],
        Awaitable[None],
    ],
) -> tuple[asyncio.AbstractServer, str]:
    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    assert server.sockets is not None
    port = server.sockets[0].getsockname()[1]
    return server, f"http://127.0.0.1:{port}"


async def respond(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    status: int,
    delay: float = 0,
) -> None:
    try:
        await reader.readuntil(b"\r\n\r\n")
        await asyncio.sleep(delay)
        writer.write(
            (f"HTTP/1.1 {status} TEST\r\nContent-Length: 0\r\nConnection: close\r\n\r\n").encode()
        )
        await writer.drain()
    finally:
        writer.close()
        await writer.wait_closed()


def fast_settings(**kwargs: object) -> MonitoringSettings:
    return MonitoringSettings.model_validate(
        {
            "retry_count": 2,
            "retry_jitter": False,
            "retry_base_delay_seconds": 0.001,
            **kwargs,
        }
    )


@pytest.mark.asyncio
async def test_transient_http_recovers() -> None:
    calls = 0

    async def handler(
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        nonlocal calls
        calls += 1
        await respond(reader, writer, 503 if calls == 1 else 200)

    server, url = await start_server(handler)
    try:
        result = (await WebsiteMonitor(fast_settings()).check_all([Website("test", url)]))[0]

        assert result.status == CheckStatus.UP
        assert result.attempts == 2
        assert calls == 2
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_permanent_404_is_not_retried() -> None:
    calls = 0

    async def handler(
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        nonlocal calls
        calls += 1
        await respond(reader, writer, 404)

    server, url = await start_server(handler)
    try:
        result = (await WebsiteMonitor(fast_settings()).check_all([Website("test", url)]))[0]

        assert result.status == CheckStatus.DOWN
        assert result.failure_category == FailureCategory.HTTP_STATUS
        assert result.http_status == 404
        assert result.attempts == 1
        assert calls == 1
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_transient_http_exhausts_retry_budget() -> None:
    calls = 0

    async def handler(
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        nonlocal calls
        calls += 1
        await respond(reader, writer, 503)

    server, url = await start_server(handler)
    try:
        result = (await WebsiteMonitor(fast_settings()).check_all([Website("test", url)]))[0]

        assert result.status == CheckStatus.DOWN
        assert result.http_status == 503
        assert result.attempts == 3
        assert calls == 3
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_timeout_retries_and_does_not_break_other_check() -> None:
    async def handler(
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        line = await reader.readline()
        try:
            await reader.readuntil(b"\r\n\r\n")
            await asyncio.sleep(0.15 if b"/slow " in line else 0)
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
            await writer.drain()
        except (ConnectionError, OSError):
            pass
        finally:
            writer.close()
            await writer.wait_closed()

    server, url = await start_server(handler)
    try:
        results = await WebsiteMonitor(fast_settings(timeout_seconds=0.03)).check_all(
            [
                Website("slow", url + "/slow"),
                Website("fast", url + "/fast"),
            ]
        )

        assert results[0].failure_category == FailureCategory.TIMEOUT
        assert results[0].attempts == 3
        assert results[1].status == CheckStatus.UP
    finally:
        server.close()
        await server.wait_closed()


def test_exponential_backoff_and_cap() -> None:
    monitor = WebsiteMonitor(
        fast_settings(
            retry_base_delay_seconds=0.2,
            retry_max_delay_seconds=0.5,
        )
    )

    assert [monitor._retry_delay(n) for n in (1, 2, 3, 4)] == [0.2, 0.4, 0.5, 0.5]


def test_jitter_is_within_bounds() -> None:
    monitor = WebsiteMonitor(fast_settings(retry_jitter=True))

    with patch(
        "sitepulse.services.monitor.random.uniform",
        return_value=0.0005,
    ) as mocked:
        assert monitor._retry_delay(1) == 0.0005
        mocked.assert_called_once_with(0.0, 0.001)


@pytest.mark.asyncio
async def test_cancellation_propagates() -> None:
    started = asyncio.Event()
    release = asyncio.Event()

    async def handler(
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        try:
            await reader.readuntil(b"\r\n\r\n")
            started.set()
            await release.wait()
        finally:
            writer.close()
            await writer.wait_closed()

    server, url = await start_server(handler)
    try:
        monitor = WebsiteMonitor(fast_settings())
        task = asyncio.create_task(monitor.check_all([Website("slow", url)]))

        await asyncio.wait_for(started.wait(), timeout=1.0)
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        release.set()
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_retry_wait_does_not_hold_semaphore() -> None:
    async def handler(
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        line = await reader.readline()
        if b"/retry " in line:
            await respond(reader, writer, 503)
        else:
            await respond(reader, writer, 200)

    server, url = await start_server(handler)
    try:
        monitor = WebsiteMonitor(
            fast_settings(
                max_concurrency=1,
                retry_base_delay_seconds=0.1,
                retry_max_delay_seconds=0.1,
            )
        )

        results = await monitor.check_all(
            [
                Website("retry", url + "/retry"),
                Website("ok", url + "/ok"),
            ]
        )

        assert results[0].attempts == 3
        assert results[1].status == CheckStatus.UP
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_dns_failure_is_not_retried() -> None:
    error = aiohttp.ClientConnectorError(
        None,
        socket.gaierror(-2, "name unavailable"),
    )

    with patch.object(
        aiohttp.ClientSession,
        "get",
        side_effect=error,
    ) as request:
        result = (
            await WebsiteMonitor(fast_settings()).check_all(
                [Website("dns", "https://example.test")]
            )
        )[0]

    assert result.failure_category == FailureCategory.DNS
    assert result.attempts == 1
    assert request.call_count == 1


@pytest.mark.asyncio
async def test_ssl_failure_is_not_retried() -> None:
    error = aiohttp.ClientSSLError(
        None,
        OSError("SSL failed"),
    )

    with patch.object(
        aiohttp.ClientSession,
        "get",
        side_effect=error,
    ) as request:
        result = (
            await WebsiteMonitor(fast_settings()).check_all(
                [Website("ssl", "https://example.test")]
            )
        )[0]

    assert result.failure_category == FailureCategory.SSL
    assert result.attempts == 1
    assert request.call_count == 1
