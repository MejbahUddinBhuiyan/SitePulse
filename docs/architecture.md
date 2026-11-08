
# SitePulse Architecture

## 1. Overview

SitePulse is a local Python command-line application that monitors website availability and records observations.

Its architecture separates:

1. Command-line interaction
2. Configuration and validation
3. Asynchronous HTTP monitoring
4. SQLite persistence
5. Statistical reporting
6. Application logging

This separation keeps monitoring logic independent from terminal presentation and database operations.

## 2. High-Level Architecture

```text
                USER
                  |
                  v
         +------------------+
         |   Typer CLI      |
         |     cli.py       |
         +------------------+
             |         |
             |         +-------------------+
             v                             v
    +------------------+        +---------------------+
    | Website Monitor  |        | Config Management   |
    | asyncio + aiohttp|        | Pydantic + JSON      |
    +------------------+        +---------------------+
             |
             v
    +------------------+
    | Check Results    |
    | UP / DOWN        |
    | HTTP / Duration  |
    | Failures/Attempts|
    +------------------+
             |
       +-----+------+
       |            |
       v            v
 +------------+  +-------------------+
 | SQLite     |  | Application Logs  |
 | History    |  | Rotating Files    |
 +------------+  +-------------------+
       |
       v
 +--------------------+
 | Reports            |
 | History / Stats    |
 | CSV / JSON         |
 +--------------------+
```

## 3. Main Modules

### `cli.py`

Defines the main Typer command-line interface.

Responsibilities:

- Website management
- One-time monitoring
- Continuous monitoring
- Rich terminal rendering
- Database selection
- Connecting the monitoring engine to storage

### `models/`

Defines the application's typed data structures.

Important models:

- `Website`
- `MonitoringResult`
- `CheckStatus`
- `FailureCategory`

MonitoringResult records the website URL, status, timestamp, HTTP status, measured duration, failure classification, error information, and attempt count.

### `services/monitor.py`

Contains the asynchronous monitoring engine.

Main responsibilities:

- HTTP requests using aiohttp
- Concurrent checks using asyncio
- Semaphore-based concurrency limits
- HTTP response classification
- DNS, connection, timeout, and SSL failure handling
- Retry decisions
- Exponential backoff and optional jitter
- Cancellation propagation

The engine makes requests concurrently instead of checking every website sequentially.

### `storage/__init__.py`

Handles registered website records in SQLite.

Its repository operations include:

- Initialization
- Adding websites
- Listing websites
- Retrieving a website
- Enabling and disabling websites
- Removing websites

### `storage/history.py`

Handles persistent monitoring observations.

Responsibilities:

- Batch result insertion
- Parameterized SQL
- Transactional persistence
- Date filtering
- Website filtering
- Recent history retrieval

### `reports/__init__.py`

Calculates monitoring statistics from stored history.

Statistics include:

- Total observations
- Successful observations
- Failed observations
- Observed success percentage
- Average, minimum, and maximum recorded check duration

It also exports summary data as CSV or JSON.

### `history_cli.py`

Provides `history` and `report` commands and displays stored data with Rich tables.

### `config.py`

Defines the Pydantic settings model.

It validates timeout values, concurrency, retry settings, HTTP status boundaries, log settings, and local file paths.

### `runtime.py`

Handles:

- Loading JSON configuration
- Saving validated configuration
- Atomic configuration-file replacement
- Configuring console logging
- Configuring rotating-file logging
- Managing SitePulse-owned logging handlers

### `config_cli.py`

Provides:

- `sitepulse config show`
- `sitepulse config set`
- `sitepulse config reset --force`

Configuration reset backs up the previous file before restoring defaults.

## 4. Monitoring Lifecycle

For a one-time monitoring command:

```text
sitepulse check
      |
      v
Resolve database path
      |
      v
Load registered websites
      |
      v
Keep enabled websites
      |
      v
Load monitoring settings
      |
      v
Configure application logging
      |
      v
Create asynchronous HTTP session
      |
      v
Run concurrent checks
      |
      v
Apply retry policy if required
      |
      v
Create MonitoringResult objects
      |
      v
Save completed results to SQLite
      |
      v
Write application log entries
      |
      v
Render Rich dashboard
```

The continuous monitor repeats this process, waiting for the configured or requested interval after completed rounds.

## 5. Concurrency Model

SitePulse uses an asyncio semaphore to limit concurrent HTTP requests.

For example:

```text
Registered websites: 100
Maximum concurrency: 10
```

The monitor can check multiple websites concurrently, but at most 10 requests should hold the semaphore simultaneously.

This helps avoid creating too many simultaneous connections.

Retries use the same monitoring engine and respect the request semaphore.

## 6. Retry Strategy

Retries are used for selected transient failures, including:

- HTTP 408
- HTTP 429
- HTTP 500
- HTTP 502
- HTTP 503
- HTTP 504
- Timeouts
- Connection failures

DNS and SSL failures, as well as HTTP 404 responses, are not retried by the current policy.

The nominal retry delay before optional jitter is:

```text
delay = min(
    base_delay * 2 ** (retry_number - 1),
    maximum_delay
)
```

When jitter is enabled, a randomized delay is chosen within the calculated cap.

The recorded check duration includes time spent waiting between attempts.

## 7. Database Design

The database uses SQLite.

### Websites table

Stores registered website information, including:

- Website ID
- Name
- URL
- Enabled state

### Monitoring results table

Stores completed observations, including:

- Result ID
- Website ID
- Check timestamp
- UP/DOWN status
- HTTP status
- Response time
- Failure category
- Error message
- Attempt count

The monitoring results table references the websites table.

Deleting a website cascades to its associated monitoring history.

Batch persistence uses parameterized statements and database transactions.

## 8. Configuration Lifecycle

```text
CLI command
    |
    v
Load sitepulse.json
    |
    v
Validate with Pydantic
    |
    +-- Valid --> Use settings
    |
    +-- Invalid --> Show configuration error
                         |
                         v
                config reset --force
                         |
                         v
                Back up previous JSON
                         |
                         v
                Restore valid defaults
```

Configuration values are resolved when commands execute, avoiding invalid JSON crashes during application import.

## 9. Logging

SitePulse uses Python's logging framework.

A console handler displays application events during execution.

A rotating-file handler writes log entries to the configured log path.

The application tracks its own handlers and replaces them during reconfiguration without intentionally removing external handlers.

Monitoring logs use website IDs and status metadata rather than the full monitored URL.

Automated CLI tests redirect logging to temporary directories so simulated checks do not pollute the actual application log.

## 10. Reliability and Testing

Automated tests cover:

- Model validation
- Configuration validation
- Website repository operations
- CLI commands
- HTTP monitoring
- Retry behavior
- Timeout and failure handling
- Persistent monitoring history
- Report calculations
- CSV and JSON export
- Logging behavior
- Configuration recovery
- SQLite transaction rollback
- Logging-handler isolation

The verified M9 baseline was 89 passing tests.

Code quality is checked using Ruff and mypy.

## 11. Limitations and Future Improvements

Current limitations:

- Local CLI execution only
- No hosted web interface
- No email or SMS alerts
- No built-in background service
- No distributed monitoring workers
- No external time-series database
- No continuously observed uptime guarantee

Potential future enhancements:

- Alerting on repeated failures
- A lightweight web dashboard
- Automated scheduling as a system service
- Notifications and alert thresholds
- Larger-scale monitoring storage
- Historical visualization
- Multi-location monitoring

These are future possibilities, not features implemented in the current release.
