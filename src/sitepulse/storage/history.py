"""Persistent monitoring history stored in the existing SQLite database."""

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite

from sitepulse.models import CheckStatus, FailureCategory, MonitoringResult, Website
from sitepulse.storage import StorageError


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    """One stored monitoring observation and its registered website."""

    id: int
    website_id: int
    website_name: str
    result: MonitoringResult


def utc_text(value: datetime) -> str:
    """Use a consistent UTC representation for SQLite time comparisons."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timestamp must be timezone-aware")

    return value.astimezone(UTC).isoformat(timespec="microseconds")


class HistoryRepository:
    """Save and retrieve checks without modifying website records."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    async def save_batch(self, records: list[tuple[Website, MonitoringResult]]) -> None:
        """Atomically store one completed monitoring batch."""
        if not records:
            return

        values: list[
            tuple[int, str, str, int | None, float | None, str | None, str | None, int]
        ] = []

        for website, result in records:
            if website.id is None:
                raise StorageError("Cannot store a result for an unsaved website")

            if website.url != result.website_url:
                raise StorageError("Website URL does not match monitoring result")

            values.append(
                (
                    website.id,
                    utc_text(result.checked_at),
                    result.status.value,
                    result.http_status,
                    result.response_time_ms,
                    result.failure_category.value if result.failure_category else None,
                    result.error_message,
                    result.attempts,
                )
            )

        try:
            async with aiosqlite.connect(self.database_path) as db:
                await db.execute("PRAGMA foreign_keys = ON")
                await db.executemany(
                    """INSERT INTO monitoring_results
                    (website_id, checked_at, status, http_status,
                     response_time_ms, failure_category, error_message, attempts)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    values,
                )
                await db.commit()

        except (sqlite3.Error, OSError) as exc:
            raise StorageError("Could not save monitoring results") from exc

    async def fetch(
        self,
        *,
        website_id: int | None = None,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[HistoryEntry]:
        """Fetch newest observations; limit=None returns all matching rows."""
        if limit is not None and limit < 1:
            raise ValueError("limit must be positive")

        conditions: list[str] = []
        params: list[int | str] = []

        if website_id is not None:
            conditions.append("r.website_id = ?")
            params.append(website_id)

        if since is not None:
            conditions.append("r.checked_at >= ?")
            params.append(utc_text(since))

        where = " WHERE " + " AND ".join(conditions) if conditions else ""

        sql = (
            "SELECT r.id, r.website_id, w.name, w.url, r.checked_at, r.status, "
            "r.http_status, r.response_time_ms, r.failure_category, "
            "r.error_message, r.attempts "
            "FROM monitoring_results AS r "
            "JOIN websites AS w ON w.id = r.website_id"
            + where
            + " ORDER BY r.checked_at DESC, r.id DESC"
        )

        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)

        try:
            async with aiosqlite.connect(self.database_path) as db:
                db.row_factory = aiosqlite.Row

                async with db.execute(sql, params) as cursor:
                    rows = await cursor.fetchall()

        except (sqlite3.Error, OSError) as exc:
            raise StorageError("Could not load monitoring history") from exc

        return [
            HistoryEntry(
                id=row["id"],
                website_id=row["website_id"],
                website_name=row["name"],
                result=MonitoringResult(
                    website_url=row["url"],
                    checked_at=datetime.fromisoformat(row["checked_at"]),
                    status=CheckStatus(row["status"]),
                    http_status=row["http_status"],
                    response_time_ms=row["response_time_ms"],
                    failure_category=(
                        FailureCategory(row["failure_category"])
                        if row["failure_category"] is not None
                        else None
                    ),
                    error_message=row["error_message"],
                    attempts=row["attempts"],
                ),
            )
            for row in rows
        ]
