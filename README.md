
# SitePulse

### Intelligent Asynchronous Website Monitoring System

A Python command-line application for checking website availability, measuring response times, storing monitoring history, and generating reports.

SitePulse uses Python's `asyncio` and `aiohttp` to monitor multiple websites concurrently. It supports retry policies, SQLite persistence, configurable monitoring settings, and rotating application logs.

Built as a Python software engineering and networking portfolio project.

## Features

- **Asynchronous HTTP monitoring** — Check multiple websites concurrently using `asyncio` and `aiohttp`.
- **Website management** — Add, list, enable, disable, or remove monitored websites.
- **Live monitoring dashboard** — View website status, HTTP status codes, response times, and retry attempts.
- **Retry mechanism** — Retry transient HTTP and connection failures using exponential backoff and optional jitter.
- **Continuous monitoring** — Run repeated checks using configurable intervals.
- **Persistent monitoring history** — Save completed checks in SQLite.
- **Monitoring statistics** — Calculate successful and failed checks, observed success percentage, and check-duration statistics.
- **CSV and JSON reports** — Export summarized monitoring results.
- **Persistent settings** — Manage configuration using a local JSON file.
- **Rotating logs** — Store application events with automatic log rotation.
- **Configuration recovery** — Back up and reset invalid settings.
- **Automated testing** — Unit, integration, and reliability tests using pytest.
- **Static code quality** — Ruff linting and formatting, with mypy type checking.

## Technology Stack

| Category | Technology |
|---|---|
| Language | Python 3.12+ |
| Async programming | asyncio |
| HTTP client | aiohttp |
| CLI | Typer |
| Terminal output | Rich |
| Configuration validation | Pydantic |
| Database | SQLite |
| Asynchronous database access | aiosqlite |
| Logging | Python logging |
| Testing | pytest and pytest-asyncio |
| Linting and formatting | Ruff |
| Type checking | mypy |

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/MejbahUddinBhuiyan/SitePulse.git
cd SitePulse
```

### 2. Create a virtual environment

On Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

On Linux or macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Make sure your virtual environment uses Python 3.12 or newer.

### 3. Install the application

```bash
python -m pip install --upgrade pip
python -m pip install -e .
```

### 4. Verify installation

```bash
sitepulse version
sitepulse doctor
sitepulse --help
```

## Quick Start

### Register a website

```bash
sitepulse add Google https://www.google.com
```

### View registered websites

```bash
sitepulse list
```

### Run a monitoring check

```bash
sitepulse check
```

Check a specific website:

```bash
sitepulse check --id 1
```

### Monitor continuously

Check websites repeatedly with a 30-second pause between rounds:

```bash
sitepulse monitor --interval 30
```

Press `Ctrl+C` to stop.

Run exactly three rounds:

```bash
sitepulse monitor --interval 5 --count 3
```

### View monitoring history

```bash
sitepulse history
sitepulse history --id 1 --hours 24
```

### Generate reports

```bash
sitepulse report
sitepulse report --id 1 --hours 48
```

Export results:

```bash
sitepulse report --format csv --output reports/report.csv
sitepulse report --format json --output reports/report.json
```

### Manage configuration

Show settings:

```bash
sitepulse config show
```

Update settings:

```bash
sitepulse config set timeout_seconds 5
sitepulse config set retry_count 3
sitepulse config set interval_seconds 15
sitepulse config set max_concurrency 20
```

Restore default settings:

```bash
sitepulse config reset --force
```

If a configuration file already exists, the reset command saves a backup to `sitepulse.json.bak`.

## Project Structure

```text
SitePulse/
├── src/
│   └── sitepulse/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── config.py
│       ├── config_cli.py
│       ├── history_cli.py
│       ├── runtime.py
│       ├── models/
│       ├── services/
│       │   └── monitor.py
│       ├── storage/
│       │   ├── __init__.py
│       │   └── history.py
│       └── reports/
│           └── __init__.py
├── tests/
├── docs/
│   ├── architecture.md
│   ├── usage.md
│   └── release-checklist.md
├── pyproject.toml
├── README.md
├── LICENSE
└── .gitignore
```

Generated SQLite databases, local settings, logs, and report exports should not be committed to the repository.

## How It Works

1. Users register websites through the CLI.
2. SitePulse loads enabled websites from SQLite.
3. The monitoring engine checks websites asynchronously.
4. Transient failures may trigger retries using exponential backoff.
5. Results are classified as UP or DOWN.
6. Completed checks are saved in SQLite.
7. The CLI displays live results using Rich.
8. History and reporting commands retrieve stored observations.
9. Application events are written to rotating log files.

For more technical details, see [Architecture](docs/architecture.md).

## Understanding Monitoring Results

A website is marked **UP** when its HTTP response code falls within the configured success range. By default, this is HTTP 200–399.

A website is marked **DOWN** for other HTTP statuses or recognized request failures.

SitePulse records total check duration, including retry waiting time when retries occur.

The displayed **observed success percentage** is calculated as:

```text
Successful recorded checks / Total recorded checks × 100
```

This statistic does not guarantee continuous availability between monitoring checks.

## Configuration

SitePulse stores user settings in `sitepulse.json` in the current working directory.

Examples of configurable values:

- Monitoring interval
- HTTP timeout
- Maximum concurrency
- Retry count
- Retry base and maximum delay
- Retry jitter
- HTTP success-status range
- SQLite database location
- Logging level
- Log rotation size and backup count

See [Usage Guide](docs/usage.md) for details.

## Security and Reliability

SitePulse includes:

- Validation of configuration values
- Parameterized SQLite operations
- Transactional monitoring-result storage
- Graceful cancellation for continuous monitoring
- Backup-based configuration recovery
- Log messages based on website IDs rather than full monitored URLs
- Automated reliability and regression tests

**Security note:** SitePulse is designed for monitoring websites you own or are authorized to check. Avoid putting passwords, access tokens, or other secrets in website URLs. Registered URLs are stored in the local database, and website names/URLs can appear in terminal output.

## Development and Testing

Install the development tools if they are not already installed:

```bash
python -m pip install pytest pytest-asyncio ruff mypy
```

Run all automated tests:

```bash
python -m pytest -q
```

Run Ruff:

```bash
python -m ruff check .
python -m ruff format --check .
```

Run mypy:

```bash
python -m mypy
```

The last verified M9 baseline was **89 passing tests**, with Ruff and mypy passing. Results should be rechecked after changes.

## Documentation

- [Usage Guide](docs/usage.md)
- [Architecture](docs/architecture.md)
- [Release Checklist](docs/release-checklist.md)

## Limitations

- SitePulse is a locally executed command-line application.
- Monitoring runs only while the check or monitor process is active.
- It does not currently provide email, SMS, or push notifications.
- It does not provide a hosted web dashboard.
- Monitoring percentages describe sampled checks, not continuous uptime.
- Monitoring data is stored locally in SQLite.

## License

See [LICENSE](LICENSE) for the repository's license terms.
