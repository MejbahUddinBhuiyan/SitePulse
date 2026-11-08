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
from sitepulse.config import MonitoringSettings
from sitepulse.models import Website, WebsiteValidationError
from sitepulse.storage import StorageError, WebsiteRepository

app = typer.Typer(
    name="sitepulse",
    help="SitePulse: intelligent website monitoring.",
    add_completion=False,
    no_args_is_help=True,
)

console = Console()
DEFAULT_DB = MonitoringSettings().database_path


def run_async[T](task: Coroutine[Any, Any, T]) -> T:
    """Run an asynchronous operation from the CLI."""
    try:
        return asyncio.run(task)
    except (StorageError, WebsiteValidationError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc


async def initialize_repository(
    database_path: Path,
) -> WebsiteRepository:
    """Initialize SQLite and return the website repository."""
    repository = WebsiteRepository(database_path)
    await repository.initialize()
    return repository


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
