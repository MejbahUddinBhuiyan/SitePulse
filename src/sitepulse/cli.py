"""Command-line interface for SitePulse."""

import asyncio
import platform
import sys
from collections.abc import Coroutine
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from sitepulse import __version__
from sitepulse.config_cli import register_config_commands
from sitepulse.history_cli import register_history_commands
from sitepulse.models import (
    CheckStatus,
    MonitoringResult,
    Website,
    WebsiteValidationError,
)
from sitepulse.runtime import (
    ConfigurationError,
    configure_logging,
    load_settings,
)
from sitepulse.services.monitor import WebsiteMonitor
from sitepulse.storage import StorageError, WebsiteRepository
from sitepulse.storage.history import HistoryRepository

app = typer.Typer(
    name="sitepulse",
    help="SitePulse: intelligent website monitoring.",
    add_completion=False,
    no_args_is_help=True,
)

console = Console()

# M8: Read the configured default database path.
DEFAULT_DB = load_settings().database_path


def run_async[T](task: Coroutine[Any, Any, T]) -> T:
    """Run an asynchronous operation from the CLI."""
    try:
        return asyncio.run(task)
    except (
        StorageError,
        WebsiteValidationError,
        ConfigurationError,
    ) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc


async def initialize_repository(
    database_path: Path,
) -> WebsiteRepository:
    """Initialize SQLite and return the website repository."""
    repository = WebsiteRepository(database_path)
    await repository.initialize()
    return repository


# ---------------------------------------------------------
# M1: Application Information
# ---------------------------------------------------------


@app.command()
def version() -> None:
    """Show the installed SitePulse version."""
    console.print(f"SitePulse {__version__}")


@app.command()
def doctor() -> None:
    """Check essential local environment information."""
    table = Table(title="SitePulse Environment")
    table.add_column("Setting", style="cyan")
    table.add_column("Value")

    table.add_row("SitePulse", __version__)
    table.add_row("Python", platform.python_version())
    table.add_row("Executable", sys.executable)
    table.add_row("Platform", platform.system())

    supported = sys.version_info >= (3, 12)

    table.add_row(
        "Python >= 3.12",
        "PASS" if supported else "FAIL",
    )

    console.print(table)

    if not supported:
        raise typer.Exit(code=1)


# ---------------------------------------------------------
# M3: Website Management
# ---------------------------------------------------------


async def add_website(
    name: str,
    url: str,
    database_path: Path,
) -> Website:
    """Validate and save a website."""
    website = Website(name=name, url=url)
    repository = await initialize_repository(database_path)
    return await repository.add(website)


@app.command("add")
def add_command(
    name: Annotated[str, typer.Argument(help="Website name")],
    url: Annotated[str, typer.Argument(help="Website URL")],
    db: Annotated[
        Path,
        typer.Option("--db", help="SQLite database path"),
    ] = DEFAULT_DB,
) -> None:
    """Register a new website."""
    website = run_async(add_website(name, url, db))

    console.print(f"[green]Added[/green] #{website.id}: {website.name} ({website.url})")


async def list_websites(
    database_path: Path,
) -> list[Website]:
    """Retrieve registered websites."""
    repository = await initialize_repository(database_path)
    return await repository.list_all()


@app.command("list")
def list_command(
    db: Annotated[
        Path,
        typer.Option("--db", help="SQLite database path"),
    ] = DEFAULT_DB,
) -> None:
    """List registered websites."""
    websites = run_async(list_websites(db))

    if not websites:
        console.print("[yellow]No websites registered yet.[/yellow]")
        return

    table = Table(title="Registered Websites")
    table.add_column("ID", justify="right")
    table.add_column("Name")
    table.add_column("URL")
    table.add_column("Enabled")

    for website in websites:
        table.add_row(
            str(website.id),
            website.name,
            website.url,
            "Yes" if website.enabled else "No",
        )

    console.print(table)


async def change_website_status(
    website_id: int,
    enabled: bool,
    database_path: Path,
) -> Website:
    """Update a website's monitoring status."""
    repository = await initialize_repository(database_path)
    return await repository.set_enabled(website_id, enabled)


@app.command("enable")
def enable_command(
    website_id: Annotated[int, typer.Argument(min=1)],
    db: Annotated[
        Path,
        typer.Option("--db"),
    ] = DEFAULT_DB,
) -> None:
    """Enable monitoring for a website."""
    website = run_async(change_website_status(website_id, True, db))

    console.print(f"[green]Enabled[/green] #{website.id}: {website.name}")


@app.command("disable")
def disable_command(
    website_id: Annotated[int, typer.Argument(min=1)],
    db: Annotated[
        Path,
        typer.Option("--db"),
    ] = DEFAULT_DB,
) -> None:
    """Disable monitoring for a website."""
    website = run_async(change_website_status(website_id, False, db))

    console.print(f"[yellow]Disabled[/yellow] #{website.id}: {website.name}")


async def delete_website(
    website_id: int,
    database_path: Path,
) -> None:
    """Remove a registered website."""
    repository = await initialize_repository(database_path)
    await repository.remove(website_id)


@app.command("remove")
def remove_command(
    website_id: Annotated[int, typer.Argument(min=1)],
    db: Annotated[
        Path,
        typer.Option("--db"),
    ] = DEFAULT_DB,
) -> None:
    """Permanently remove a website."""
    run_async(delete_website(website_id, db))

    console.print(f"[green]Removed[/green] website #{website_id}")


# ---------------------------------------------------------
# M6: Monitoring CLI
# M7: Persistent Monitoring History
# M8: Configurable Monitoring and Logging
# ---------------------------------------------------------


async def run_monitoring_batch(
    database_path: Path,
    website_id: int | None = None,
) -> list[tuple[Website, MonitoringResult]]:
    """Check enabled websites and save results to SQLite."""
    repository = await initialize_repository(database_path)

    if website_id is None:
        websites = await repository.list_all()
    else:
        websites = [await repository.get(website_id)]

    enabled = [website for website in websites if website.enabled]

    if not enabled:
        return []

    # M8: Apply saved monitoring configuration.
    settings = load_settings()
    logger = configure_logging(settings)

    monitor = WebsiteMonitor(settings)
    results = await monitor.check_all(enabled)

    records = list(zip(enabled, results, strict=True))

    # M7: Persist completed monitoring results.
    await HistoryRepository(database_path).save_batch(records)

    # M8: Log IDs and check information, not full URLs.
    for website, result in records:
        logger.info(
            "website_id=%s status=%s http=%s attempts=%s",
            website.id,
            result.status.value,
            result.http_status,
            result.attempts,
        )

    return records


def render_monitoring_results(
    records: list[tuple[Website, MonitoringResult]],
) -> None:
    """Display website monitoring results using Rich."""
    if not records:
        console.print("[yellow]No enabled websites to check.[/yellow]")
        return

    table = Table(title="SitePulse Monitoring Dashboard")

    table.add_column("ID", justify="right")
    table.add_column("Website")
    table.add_column("Status")
    table.add_column("HTTP", justify="right")
    table.add_column("Time (ms)", justify="right")
    table.add_column("Attempts", justify="right")
    table.add_column("Failure")
    table.add_column("Checked (UTC)")

    up_count = 0

    for website, result in records:
        is_up = result.status == CheckStatus.UP

        if is_up:
            up_count += 1

        status = "[green]UP[/green]" if is_up else "[red]DOWN[/red]"

        http_status = str(result.http_status) if result.http_status is not None else "-"

        response_time = (
            f"{result.response_time_ms:.2f}" if result.response_time_ms is not None else "-"
        )

        failure = result.failure_category.value if result.failure_category is not None else "-"

        table.add_row(
            str(website.id),
            website.name,
            status,
            http_status,
            response_time,
            str(result.attempts),
            failure,
            result.checked_at.strftime("%Y-%m-%d %H:%M:%S"),
        )

    console.print(table)

    total = len(records)
    down_count = total - up_count

    console.print(f"[green]UP: {up_count}[/green] | [red]DOWN: {down_count}[/red] | Total: {total}")

    console.print("[dim]Response time includes retry delays. Results are saved to SQLite.[/dim]")


@app.command("check")
def check_command(
    website_id: Annotated[
        int | None,
        typer.Option(
            "--id",
            min=1,
            help="Check only the selected website ID",
        ),
    ] = None,
    db: Annotated[
        Path,
        typer.Option(
            "--db",
            help="SQLite database path",
        ),
    ] = DEFAULT_DB,
) -> None:
    """Run one monitoring check for enabled websites."""
    records = run_async(run_monitoring_batch(db, website_id))

    render_monitoring_results(records)


async def continuous_monitoring(
    database_path: Path,
    website_id: int | None,
    interval: float | None,
    count: int,
) -> None:
    """Monitor repeatedly using configured or explicit intervals."""
    completed = 0

    while count == 0 or completed < count:
        console.print(f"\n[bold cyan]Monitoring round {completed + 1}[/bold cyan]")

        records = await run_monitoring_batch(
            database_path,
            website_id,
        )

        render_monitoring_results(records)

        completed += 1

        if count != 0 and completed >= count:
            break

        # M8: Use the saved interval unless overridden by --interval.
        pause = interval if interval is not None else load_settings().interval_seconds

        await asyncio.sleep(pause)


@app.command("monitor")
def monitor_command(
    website_id: Annotated[
        int | None,
        typer.Option(
            "--id",
            min=1,
            help="Monitor one website ID",
        ),
    ] = None,
    interval: Annotated[
        float | None,
        typer.Option(
            "--interval",
            min=0.01,
            help="Seconds between monitoring rounds",
        ),
    ] = None,
    count: Annotated[
        int,
        typer.Option(
            "--count",
            min=0,
            help="Number of rounds; 0 means continuous",
        ),
    ] = 0,
    db: Annotated[
        Path,
        typer.Option(
            "--db",
            help="SQLite database path",
        ),
    ] = DEFAULT_DB,
) -> None:
    """Monitor websites repeatedly; press Ctrl+C to stop."""
    console.print("[cyan]Starting SitePulse monitoring...[/cyan]")

    try:
        run_async(
            continuous_monitoring(
                db,
                website_id,
                interval,
                count,
            )
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Monitoring stopped by user.[/yellow]")
        raise typer.Exit(code=130) from None

    console.print("[green]Monitoring finished.[/green]")


# ---------------------------------------------------------
# M7: History and Reporting Commands
# M8: Configuration Commands
# ---------------------------------------------------------


register_history_commands(app)
register_config_commands(app)
