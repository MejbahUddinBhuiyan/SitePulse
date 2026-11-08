# Architecture

## M1 — Installable CLI skeleton

```text
PowerShell -> Typer CLI -> Rich output
```

The `src/` layout ensures tests import the installed package instead of relying on the working directory. `pyproject.toml` is the single packaging and tooling configuration file.

## Planned (not yet implemented)

```text
CLI -> Services -> aiohttp website checks
              -> SQLite repositories (aiosqlite)
              -> report aggregation / export
```

The future monitoring engine will use bounded concurrency, explicit network error categories, persistent per-check data, and safe cancellation. These parts will be added and tested milestone by milestone.
