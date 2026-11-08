"""History and reporting commands for SitePulse."""

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal

import typer
from rich.console import Console
from rich.table import Table

from sitepulse.reports import export_summaries, summarize
from sitepulse.storage import StorageError, WebsiteRepository
from sitepulse.storage.history import HistoryEntry, HistoryRepository

console = Console()
DEFAULT_DB = Path("sitepulse.db")


async def load_history(
    db: Path,
    website_id: int | None,
    hours: float,
    limit: int | None,
) -> list[HistoryEntry]:
    """Read history after verifying the selected website exists."""
    repository = WebsiteRepository(db)
    await repository.initialize()

    if website_id is not None:
        await repository.get(website_id)

    since = datetime.now(UTC) - timedelta(hours=hours)

    return await HistoryRepository(db).fetch(
        website_id=website_id,
        since=since,
        limit=limit,
    )


def register_history_commands(app: typer.Typer) -> None:
    """Register M7 commands with the existing CLI."""

    @app.command("history")
    def history_command(
        website_id: Annotated[
            int | None,
            typer.Option("--id", min=1),
        ] = None,
        hours: Annotated[
            float,
            typer.Option("--hours", min=0.01),
        ] = 24.0,
        limit: Annotated[
            int,
            typer.Option("--limit", min=1),
        ] = 20,
        db: Annotated[
            Path,
            typer.Option("--db"),
        ] = DEFAULT_DB,
    ) -> None:
        """Show the most recent recorded website checks."""
        try:
            entries = asyncio.run(load_history(db, website_id, hours, limit))
        except StorageError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(code=1) from exc

        if not entries:
            console.print("[yellow]No checks recorded in this time window.[/yellow]")
            return

        table = Table(title="SitePulse Monitoring History")

        for heading in (
            "ID",
            "Website",
            "Status",
            "HTTP",
            "Time (ms)",
            "Attempts",
            "UTC",
        ):
            table.add_column(heading)

        for entry in entries:
            result = entry.result

            table.add_row(
                str(entry.website_id),
                entry.website_name,
                result.status.value.upper(),
                str(result.http_status) if result.http_status is not None else "-",
                f"{result.response_time_ms:.2f}" if result.response_time_ms is not None else "-",
                str(result.attempts),
                result.checked_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S"),
            )

        console.print(table)

    @app.command("report")
    def report_command(
        website_id: Annotated[
            int | None,
            typer.Option("--id", min=1),
        ] = None,
        hours: Annotated[
            float,
            typer.Option("--hours", min=0.01),
        ] = 24.0,
        output_format: Annotated[
            Literal["table", "csv", "json"],
            typer.Option("--format"),
        ] = "table",
        output: Annotated[
            Path | None,
            typer.Option("--output"),
        ] = None,
        db: Annotated[
            Path,
            typer.Option("--db"),
        ] = DEFAULT_DB,
    ) -> None:
        """Summarize observed checks and optionally export CSV or JSON."""
        if output_format != "table" and output is None:
            console.print("[red]Error:[/red] --output is required for CSV/JSON")
            raise typer.Exit(code=2)

        try:
            entries = asyncio.run(load_history(db, website_id, hours, None))

            summaries = summarize(entries)

            if output_format != "table":
                assert output is not None

                export_summaries(
                    output,
                    summaries,
                    output_format,
                )

                console.print(
                    f"[green]Exported[/green] {len(summaries)} website summaries to {output}"
                )
                return

        except (StorageError, OSError) as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(code=1) from exc

        if not summaries:
            console.print("[yellow]No checks recorded in this time window.[/yellow]")
            return

        table = Table(title=f"SitePulse Report — last {hours:g} hours")

        for heading in (
            "Website",
            "Checks",
            "UP",
            "DOWN",
            "Observed %",
            "Avg ms",
            "Min ms",
            "Max ms",
        ):
            table.add_column(heading)

        def display(number: float | None) -> str:
            return f"{number:.2f}" if number is not None else "-"

        for summary in summaries:
            table.add_row(
                summary.website_name,
                str(summary.checks),
                str(summary.successful),
                str(summary.failed),
                f"{summary.observed_success_percent:.2f}%",
                display(summary.average_ms),
                display(summary.minimum_ms),
                display(summary.maximum_ms),
            )

        console.print(table)

        console.print(
            "[dim]Observed % = successful checks / total checks; not continuous uptime.[/dim]"
        )
