
# SitePulse Usage Guide

This guide explains how to use SitePulse from the command line.

## 1. Check Your Environment

Activate the virtual environment and run:

```powershell
sitepulse version
sitepulse doctor
sitepulse --help
```

SitePulse requires Python 3.12 or newer.

## 2. Register a Website

Syntax:

```powershell
sitepulse add NAME URL
```

Example:

```powershell
sitepulse add Google https://www.google.com
sitepulse add Python https://www.python.org
```

Each website receives an integer ID in SQLite.

The same URL cannot be registered twice in the same database.

## 3. Manage Websites

List websites:

```powershell
sitepulse list
```

Enable a website:

```powershell
sitepulse enable 1
```

Disable a website:

```powershell
sitepulse disable 1
```

Remove a website:

```powershell
sitepulse remove 1
```

**Warning:** Removing a registered website also deletes its associated monitoring history because the SQLite relationship uses cascading deletion.

## 4. Check Website Availability

Check all enabled websites:

```powershell
sitepulse check
```

Check one website:

```powershell
sitepulse check --id 1
```

The monitoring table displays:

| Field | Meaning |
|---|---|
| ID | Registered website identifier |
| Website | Website name |
| Status | UP or DOWN |
| HTTP | Returned HTTP status code, if available |
| Time (ms) | Total check duration |
| Attempts | Number of HTTP attempts |
| Failure | Classified failure type |
| Checked (UTC) | Check timestamp in UTC |

Disabled websites are skipped.

The default success HTTP range is 200–399.

## 5. Continuous Monitoring

Start continuous monitoring:

```powershell
sitepulse monitor
```

Use a specific interval:

```powershell
sitepulse monitor --interval 10
```

Run a fixed number of rounds:

```powershell
sitepulse monitor --interval 5 --count 3
```

Monitor one website:

```powershell
sitepulse monitor --id 1 --interval 10
```

Stop continuous monitoring using `Ctrl+C`.

The interval is the pause after one monitoring round finishes, not the exact time between the start of consecutive rounds.

## 6. Monitoring History

Display the most recent checks:

```powershell
sitepulse history
```

Filter by website ID:

```powershell
sitepulse history --id 1
```

Filter by time window:

```powershell
sitepulse history --hours 48
```

Limit displayed rows:

```powershell
sitepulse history --limit 10
```

Combine filters:

```powershell
sitepulse history --id 1 --hours 24 --limit 20
```

By default, history displays up to 20 checks from the previous 24 hours.

## 7. Reports

Generate a report for all websites with matching recorded checks:

```powershell
sitepulse report
```

Report on one website:

```powershell
sitepulse report --id 1
```

Report on the previous 48 hours:

```powershell
sitepulse report --hours 48
```

Reports include:

- Total recorded checks
- Successful checks
- Failed checks
- Observed success percentage
- Average recorded check duration
- Minimum recorded check duration
- Maximum recorded check duration

If a website has no checks in the selected time window, it will not appear in the report.

### Export CSV

```powershell
sitepulse report --format csv --output reports/report.csv
```

### Export JSON

```powershell
sitepulse report --format json --output reports/report.json
```

The exported data contains summarized statistics for each website, not individual raw monitoring events.

## 8. Configuration

Show the current configuration:

```powershell
sitepulse config show
```

Update a setting:

```powershell
sitepulse config set timeout_seconds 5
```

Additional examples:

```powershell
sitepulse config set interval_seconds 30
sitepulse config set max_concurrency 20
sitepulse config set retry_count 3
sitepulse config set retry_jitter false
sitepulse config set log_level DEBUG
```

Some important settings:

| Setting | Default | Description |
|---|---|---|
| interval_seconds | 60 | Pause between monitoring rounds |
| timeout_seconds | 10 | HTTP request timeout |
| max_concurrency | 10 | Maximum concurrent requests |
| retry_count | 2 | Maximum additional attempts |
| retry_base_delay_seconds | 0.5 | Starting retry backoff |
| retry_max_delay_seconds | 10 | Backoff cap |
| retry_jitter | true | Add randomness to retry timing |
| success_status_min | 200 | Minimum successful HTTP status |
| success_status_max | 399 | Maximum successful HTTP status |
| database_path | sitepulse.db | Local SQLite database |
| log_level | INFO | Application logging threshold |
| log_file | logs/sitepulse.log | Rotating log file |
| log_max_bytes | 1048576 | Maximum active log size |
| log_backup_count | 3 | Number of rotated backups |

Changes are validated before being saved.

The configured monitoring interval is used when `--interval` is omitted. An explicit CLI interval takes priority.

Changing `database_path` points SitePulse to a different database on the next CLI invocation. It does not migrate existing records automatically.

## 9. Configuration Recovery

If the configuration contains invalid JSON, commands that require settings report an error.

Help and version commands remain available:

```powershell
sitepulse --help
sitepulse version
```

To back up the existing configuration and restore defaults:

```powershell
sitepulse config reset --force
```

This creates `sitepulse.json.bak` when an existing configuration file is present.

**Important:** Resetting configuration restores the default database path. It does not delete your previous database. If you had configured a custom database location, set that location again after recovery.

A later reset can replace the existing backup.

## 10. Logging

By default, application logs are written to:

```text
logs/sitepulse.log
```

Read the last 10 lines in PowerShell:

```powershell
Get-Content logs/sitepulse.log -Tail 10
```

The active log file rotates when it reaches its configured size.

Normal monitoring log entries include website ID, result status, HTTP status, and attempt count.

The application does not intentionally include full monitored URLs in its own monitoring log entries.

## 11. Use a Different Database

You can provide a database file explicitly:

```powershell
sitepulse add Test https://example.com --db alternate.db
sitepulse list --db alternate.db
sitepulse check --db alternate.db
sitepulse history --db alternate.db
sitepulse report --db alternate.db
```

The `--db` option overrides the configured default database for that command.

## 12. Troubleshooting

### `sitepulse` command not found

Activate your virtual environment, then reinstall the package:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

### No websites registered

Add a website:

```powershell
sitepulse add Google https://www.google.com
```

### No enabled websites to check

Run:

```powershell
sitepulse list
```

Enable a disabled website:

```powershell
sitepulse enable 1
```

### No checks recorded

Perform a monitoring check first:

```powershell
sitepulse check
sitepulse history
```

### Configuration error

Check the configuration file or reset it:

```powershell
sitepulse config reset --force
```

### Website marked DOWN

Possible causes include HTTP errors, network connection failures, DNS errors, TLS/SSL errors, and timeouts.

A DOWN result is an observation made by SitePulse. It does not by itself prove that a website is unavailable to every user worldwide.

### Monitoring stops after closing the terminal

This is expected. SitePulse does not run as a background system service unless it is started and managed by an external process or scheduler.

## 13. Useful Test Commands

```powershell
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m pytest -q
```

See the main README and release checklist for final project verification.
