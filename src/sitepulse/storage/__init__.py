"""Async SQLite persistence for SitePulse."""

import sqlite3
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import aiosqlite

from sitepulse.models import Website


class StorageError(Exception):
    """Base exception for database operations."""


class DuplicateWebsiteError(StorageError):
    """Raised when a website URL already exists."""


class WebsiteNotFoundError(StorageError):
    """Raised when a website ID does not exist."""


def website_key(url: str) -> str:
    """Create a comparable URL key for duplicate detection."""
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    hostname = (parts.hostname or "").lower()
    port = parts.port

    if ":" in hostname:
        hostname = f"[{hostname}]"

    if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
        port = None

    authority = hostname
    if port is not None:
        authority = f"{hostname}:{port}"

    path = parts.path.rstrip("/") or "/"

    return urlunsplit((scheme, authority, path, parts.query, ""))


class WebsiteRepository:
    """Manage persisted website records using SQLite."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    async def initialize(self) -> None:
        """Create database tables and indexes if absent."""
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            async with aiosqlite.connect(self.database_path) as db:
                await db.execute("PRAGMA foreign_keys = ON")

                await db.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS websites (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        url TEXT NOT NULL,
                        url_key TEXT NOT NULL UNIQUE,
                        enabled INTEGER NOT NULL DEFAULT 1
                            CHECK (enabled IN (0, 1)),
                        created_at TEXT NOT NULL
                            DEFAULT CURRENT_TIMESTAMP
                    );

                    CREATE INDEX IF NOT EXISTS
                        idx_websites_enabled
                        ON websites(enabled);

                    CREATE TABLE IF NOT EXISTS
                        monitoring_results (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            website_id INTEGER NOT NULL,
                            checked_at TEXT NOT NULL,
                            status TEXT NOT NULL
                                CHECK (status IN ('up', 'down')),
                            http_status INTEGER,
                            response_time_ms REAL,
                            failure_category TEXT,
                            error_message TEXT,
                            attempts INTEGER NOT NULL DEFAULT 1,
                            FOREIGN KEY (website_id)
                                REFERENCES websites(id)
                                ON DELETE CASCADE
                        );

                    CREATE INDEX IF NOT EXISTS
                        idx_results_website_time
                        ON monitoring_results(
                            website_id, checked_at
                        );
                    """
                )

                await db.commit()
        except (sqlite3.Error, OSError) as exc:
            raise StorageError("Could not initialize database") from exc

    async def add(self, website: Website) -> Website:
        """Insert a new website and return its stored ID."""
        key = website_key(website.url)

        try:
            async with aiosqlite.connect(self.database_path) as db:
                cursor = await db.execute(
                    """
                    INSERT INTO websites
                        (name, url, url_key, enabled)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        website.name,
                        website.url,
                        key,
                        int(website.enabled),
                    ),
                )
                await db.commit()
                website_id = cursor.lastrowid

        except sqlite3.IntegrityError as exc:
            raise DuplicateWebsiteError("This website is already registered") from exc
        except (sqlite3.Error, OSError) as exc:
            raise StorageError("Could not save website") from exc

        if website_id is None:
            raise StorageError("Database did not return a website ID")

        return Website(
            id=website_id,
            name=website.name,
            url=website.url,
            enabled=website.enabled,
        )

    async def list_all(self) -> list[Website]:
        """Return all websites ordered by their IDs."""
        try:
            async with aiosqlite.connect(self.database_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    """
                    SELECT id, name, url, enabled
                    FROM websites
                    ORDER BY id
                    """
                ) as cursor:
                    rows = await cursor.fetchall()

        except (sqlite3.Error, OSError) as exc:
            raise StorageError("Could not load websites") from exc

        return [
            Website(
                id=row["id"],
                name=row["name"],
                url=row["url"],
                enabled=bool(row["enabled"]),
            )
            for row in rows
        ]

    async def get(self, website_id: int) -> Website:
        """Find a website by its database ID."""
        try:
            async with aiosqlite.connect(self.database_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    """
                    SELECT id, name, url, enabled
                    FROM websites
                    WHERE id = ?
                    """,
                    (website_id,),
                ) as cursor:
                    row = await cursor.fetchone()

        except (sqlite3.Error, OSError) as exc:
            raise StorageError("Could not retrieve website") from exc

        if row is None:
            raise WebsiteNotFoundError(f"Website ID {website_id} was not found")

        return Website(
            id=row["id"],
            name=row["name"],
            url=row["url"],
            enabled=bool(row["enabled"]),
        )

    async def set_enabled(self, website_id: int, enabled: bool) -> Website:
        """Enable or disable a registered website."""
        try:
            async with aiosqlite.connect(self.database_path) as db:
                cursor = await db.execute(
                    """
                    UPDATE websites
                    SET enabled = ?
                    WHERE id = ?
                    """,
                    (int(enabled), website_id),
                )
                await db.commit()
                changed = cursor.rowcount

        except (sqlite3.Error, OSError) as exc:
            raise StorageError("Could not update website") from exc

        if changed == 0:
            raise WebsiteNotFoundError(f"Website ID {website_id} was not found")

        return await self.get(website_id)

    async def remove(self, website_id: int) -> None:
        """Delete a website from SQLite."""
        try:
            async with aiosqlite.connect(self.database_path) as db:
                await db.execute("PRAGMA foreign_keys = ON")
                cursor = await db.execute(
                    "DELETE FROM websites WHERE id = ?",
                    (website_id,),
                )
                await db.commit()
                changed = cursor.rowcount

        except (sqlite3.Error, OSError) as exc:
            raise StorageError("Could not delete website") from exc

        if changed == 0:
            raise WebsiteNotFoundError(f"Website ID {website_id} was not found")
