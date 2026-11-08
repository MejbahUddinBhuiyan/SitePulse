"""Tests for persistent website management."""

from pathlib import Path

import pytest

from sitepulse.models import Website
from sitepulse.storage import (
    DuplicateWebsiteError,
    WebsiteNotFoundError,
    WebsiteRepository,
    website_key,
)


@pytest.fixture
def repository(tmp_path: Path) -> WebsiteRepository:
    return WebsiteRepository(tmp_path / "test.db")


@pytest.mark.asyncio
async def test_add_and_get(
    repository: WebsiteRepository,
) -> None:
    await repository.initialize()

    saved = await repository.add(Website("Google", "https://google.com"))

    assert saved.id is not None
    assert saved.name == "Google"

    loaded = await repository.get(saved.id)
    assert loaded == saved


@pytest.mark.asyncio
async def test_persistence(
    repository: WebsiteRepository,
) -> None:
    await repository.initialize()
    await repository.add(Website("GitHub", "https://github.com"))

    second_repository = WebsiteRepository(repository.database_path)

    websites = await second_repository.list_all()

    assert len(websites) == 1
    assert websites[0].name == "GitHub"


@pytest.mark.asyncio
async def test_duplicate_url(
    repository: WebsiteRepository,
) -> None:
    await repository.initialize()

    await repository.add(Website("First", "https://example.com/"))

    with pytest.raises(DuplicateWebsiteError):
        await repository.add(Website("Second", "https://EXAMPLE.COM"))


@pytest.mark.asyncio
async def test_enable_disable(
    repository: WebsiteRepository,
) -> None:
    await repository.initialize()

    saved = await repository.add(Website("Example", "https://example.com"))
    assert saved.id is not None

    disabled = await repository.set_enabled(saved.id, False)
    assert disabled.enabled is False

    enabled = await repository.set_enabled(saved.id, True)
    assert enabled.enabled is True


@pytest.mark.asyncio
async def test_remove(
    repository: WebsiteRepository,
) -> None:
    await repository.initialize()

    saved = await repository.add(Website("Example", "https://example.com"))
    assert saved.id is not None

    await repository.remove(saved.id)

    assert await repository.list_all() == []

    with pytest.raises(WebsiteNotFoundError):
        await repository.get(saved.id)


@pytest.mark.asyncio
async def test_missing_website(
    repository: WebsiteRepository,
) -> None:
    await repository.initialize()

    with pytest.raises(WebsiteNotFoundError):
        await repository.set_enabled(999, False)

    with pytest.raises(WebsiteNotFoundError):
        await repository.remove(999)


@pytest.mark.asyncio
async def test_initialize_is_repeatable(
    repository: WebsiteRepository,
) -> None:
    await repository.initialize()
    await repository.initialize()

    assert await repository.list_all() == []


def test_url_key_normalization() -> None:
    assert website_key("https://EXAMPLE.COM:443/path/") == website_key("https://example.com/path")
