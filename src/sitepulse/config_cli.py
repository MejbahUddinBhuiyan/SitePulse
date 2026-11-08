"""Configuration management commands."""

import json
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
    """Update one setting and save the validated configuration."""
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


def register_config_commands(app: typer.Typer) -> None:
    """Attach config commands to the main application."""
    app.add_typer(config_app, name="config")
