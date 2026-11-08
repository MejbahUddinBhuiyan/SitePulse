# SitePulse

**Status: Milestone 1 complete (project scaffold).** SitePulse is a Python-only CLI project that will monitor websites concurrently, persist history, and produce observed-availability reports. **Monitoring is not implemented yet.**

## Requirements

- Python 3.12 or newer
- Windows PowerShell (recommended) and VS Code
- Internet access for installing Python packages

## Setup on Windows (PowerShell)

```powershell
cd path\to\SitePulse
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

If `py -3.12` is unavailable, run `py -0p` to see installed Python versions. You may use `py -3.13 -m venv .venv` if Python 3.13 is installed.

If PowerShell blocks activation, use the venv Python executable directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\sitepulse.exe --help
```

## Working CLI commands (M1)

```powershell
sitepulse --help
sitepulse version
sitepulse doctor
python -m sitepulse --help
```

Example output:

```text
SitePulse 0.1.0
```

The `doctor` command shows Python version, executable, platform, and version compatibility.

## Quality checks

```powershell
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy
```

## Project architecture

The installable `src/sitepulse` package contains the Typer CLI. Future milestones will add typed models and settings, SQLite repositories, asynchronous HTTP monitoring, reporting, and robust logging. See [docs/architecture.md](docs/architecture.md).

## Planned features

Website management; aiohttp + asyncio concurrency; SSL/DNS/timeout classification; retries and backoff; aiosqlite; Rich reports; CSV/JSON exports; logging and configuration; offline tests.

## Progress

- [x] M1: environment scaffold, package, CLI smoke tests, documentation
- [ ] M2: typed models and configuration
- [ ] M3: website management and SQLite
- [ ] M4: async monitoring engine
- [ ] M5: error handling, retry, graceful cancellation
- [ ] M6: CLI dashboard and website commands
- [ ] M7: history and reports
- [ ] M8: logs and configuration CLI
- [ ] M9: full tests and static validation
- [ ] M10: final documentation, review, and clean-install audit

## License

MIT. See [LICENSE](LICENSE).
