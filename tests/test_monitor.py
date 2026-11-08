"""Local-server tests for the asynchronous HTTP monitoring engine."""

import asyncio
from collections.abc import Awaitable, Callable

import pytest

from sitepulse.config import MonitoringSettings
from sitepulse.models import (
    CheckStatus,
    FailureCategory,
    Website,
)
from sitepulse.services.monitor import WebsiteMonitor


async def serve(
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
    status: int = 200,
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


@pytest.mark.asyncio
async def test_success_and_http_failure() -> None:
    async def routed(
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        line = await reader.readline()
        await respond(
            reader,
            writer,
            200 if b"/ok " in line else 503,
        )

    server, url = await serve(routed)

    try:
        results = await WebsiteMonitor(MonitoringSettings()).check_all(
            [
                Website("good", url + "/ok"),
                Website("bad", url + "/fail"),
            ]
        )

        assert [r.status for r in results] == [
            CheckStatus.UP,
            CheckStatus.DOWN,
        ]
        assert results[0].http_status == 200
        assert results[1].failure_category == FailureCategory.HTTP_STATUS
        assert all(r.response_time_ms is not None for r in results)
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_timeout_does_not_break_other_site() -> None:
    async def handler(
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        line = await reader.readline()
        try:
            await respond(
                reader,
                writer,
                delay=0.2 if b"/slow " in line else 0,
            )
        except (ConnectionError, OSError):
            pass  # Timed-out clients may close the connection.

    server, url = await serve(handler)

    try:
        monitor = WebsiteMonitor(MonitoringSettings(timeout_seconds=0.05))

        results = await monitor.check_all(
            [
                Website("slow", url + "/slow"),
                Website("fast", url + "/fast"),
            ]
        )

        assert results[0].failure_category == FailureCategory.TIMEOUT
        assert results[1].status == CheckStatus.UP
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_disabled_websites_are_skipped() -> None:
    monitor = WebsiteMonitor(MonitoringSettings())

    assert (
        await monitor.check_all(
            [
                Website(
                    "off",
                    "http://example.com",
                    enabled=False,
                )
            ]
        )
        == []
    )


@pytest.mark.asyncio
async def test_concurrency_limit() -> None:
    active = 0
    max_active = 0

    async def handler(
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        nonlocal active, max_active

        active += 1
        max_active = max(max_active, active)

        try:
            await respond(reader, writer, delay=0.03)
        finally:
            active -= 1

    server, url = await serve(handler)

    try:
        monitor = WebsiteMonitor(MonitoringSettings(max_concurrency=2))

        results = await monitor.check_all([Website(str(i), f"{url}/{i}") for i in range(6)])

        assert len(results) == 6
        assert all(result.status == CheckStatus.UP for result in results)
        assert 1 < max_active <= 2
    finally:
        server.close()
        await server.wait_closed()
