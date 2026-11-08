"""Command-line entry point for SitePulse.

M1 deliberately only implements version and environment diagnostics.
"""

import platform
import sys

import typer
from rich.console import Console
from rich.table import Table

from sitepulse import __version__

app = typer.Typer(
    name="sitepulse",
    help="SitePulse: intelligent website monitoring (M1 scaffold).",
    add_completion=False,
    no_args_is_help=True,
)
console = Console()


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
    is_supported = sys.version_info >= (3, 12)
    table.add_row("Python >= 3.12", "PASS" if is_supported else "FAIL")
    console.print(table)
    if not is_supported:
        raise typer.Exit(code=1)
