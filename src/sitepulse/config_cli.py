"""Configuration management commands."""

import json
import shutil
from pathlib import Path
from typing import Annotated, Any

import typer
from pydantic import ValidationError
from rich.console import Console

from sitepulse.config import MonitoringSettings
from sitepulse.runtime import (
    CONFIG_PATH,
    ConfigurationError,
    load_settings,
    save_settings,
)

console = Console()

config_app = typer.Typer(
    help="View and modify persistent monitoring settings.",
    no_args_is_help=True,
)


@config_app.command("show")
def show_config(
    file: Annotated[
        Path,
        typer.Option("--file", help="Configuration file"),
    ] = CONFIG_PATH,
) -> None:
    """Display the current validated configuration."""
    try:
        settings = load_settings(file)
    except ConfigurationError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print_json(settings.model_dump_json(indent=2))


@config_app.command("set")
def set_config(
    key: Annotated[str, typer.Argument()],
    value: Annotated[str, typer.Argument()],
    file: Annotated[
        Path,
        typer.Option("--file", help="Configuration file"),
    ] = CONFIG_PATH,
) -> None:
    """Update one setting and save validated configuration."""
    try:
        settings = load_settings(file)
        data: dict[str, Any] = settings.model_dump(mode="json")

        if key not in data:
            console.print(f"[red]Unknown setting:[/red] {key}")
            raise typer.Exit(code=2)

        try:
            parsed: Any = json.loads(value)
        except json.JSONDecodeError:
            parsed = value

        data[key] = parsed

        updated = MonitoringSettings.model_validate(data)
        save_settings(updated, file)

    except (ConfigurationError, ValidationError) as exc:
        console.print(f"[red]Invalid configuration:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print(f"[green]Updated[/green] {key}")


@config_app.command("reset")
def reset_config(
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Confirm replacement of the current configuration",
        ),
    ] = False,
    file: Annotated[
        Path,
        typer.Option("--file", help="Configuration file"),
    ] = CONFIG_PATH,
) -> None:
    """Back up existing settings and restore defaults."""
    if not force:
        console.print(
            "[yellow]Configuration was not changed. Use --force to confirm reset.[/yellow]"
        )
        raise typer.Exit(code=2)

    backup = file.with_name(file.name + ".bak")

    try:
        if file.exists():
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, backup)

        save_settings(MonitoringSettings(), file)

    except (ConfigurationError, OSError) as exc:
        console.print(f"[red]Could not reset configuration:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print("[green]Configuration restored to defaults.[/green]")

    if backup.exists():
        console.print(f"Backup: {backup}")


def register_config_commands(app: typer.Typer) -> None:
    """Attach configuration commands to SitePulse."""
    app.add_typer(config_app, name="config")
