"""Statistics and export helpers for observed monitoring checks."""

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from sitepulse.storage.history import HistoryEntry


@dataclass(frozen=True, slots=True)
class CheckSummary:
    website_id: int
    website_name: str
    checks: int
    successful: int
    failed: int
    observed_success_percent: float
    average_ms: float | None
    minimum_ms: float | None
    maximum_ms: float | None


def summarize(entries: list[HistoryEntry]) -> list[CheckSummary]:
    """Summarize sampled checks, not continuous uptime."""
    by_site: dict[int, list[HistoryEntry]] = {}

    for entry in entries:
        by_site.setdefault(entry.website_id, []).append(entry)

    summaries: list[CheckSummary] = []

    for site_id, rows in sorted(by_site.items()):
        success = sum(row.result.status.value == "up" for row in rows)

        times: list[float] = []

        for row in rows:
            value = row.result.response_time_ms

            if value is not None:
                times.append(value)

        summaries.append(
            CheckSummary(
                website_id=site_id,
                website_name=rows[0].website_name,
                checks=len(rows),
                successful=success,
                failed=len(rows) - success,
                observed_success_percent=100 * success / len(rows),
                average_ms=sum(times) / len(times) if times else None,
                minimum_ms=min(times) if times else None,
                maximum_ms=max(times) if times else None,
            )
        )

    return summaries


def export_summaries(
    path: Path,
    summaries: list[CheckSummary],
    output_format: str,
) -> None:
    """Export calculated summaries as CSV or JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [asdict(item) for item in summaries]

    if output_format == "json":
        with path.open("w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2, ensure_ascii=False)
            stream.write("\n")

    elif output_format == "csv":
        with path.open(
            "w",
            newline="",
            encoding="utf-8-sig",
        ) as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=list(CheckSummary.__dataclass_fields__),
            )
            writer.writeheader()

            for item in data:
                # Avoid CSV formula injection in spreadsheet software.
                if str(item["website_name"]).startswith(("=", "+", "-", "@", "\t", "\r")):
                    item["website_name"] = "'" + str(item["website_name"])

                writer.writerow(item)

    else:
        raise ValueError("Export format must be 'csv' or 'json'")
