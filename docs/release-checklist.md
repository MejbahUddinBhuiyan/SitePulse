
# SitePulse Release Checklist

This checklist must be completed before publishing a release.

## 1. Source Code

- [ ] All required source files are present.
- [ ] No temporary debugging code remains.
- [ ] No unnecessary dependencies were added.
- [ ] Application version is correct.
- [ ] `sitepulse --help` works.

## 2. Code Quality

Run:

```powershell
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m pytest -q
```

- [ ] Ruff lint passes.
- [ ] Ruff formatting passes.
- [ ] mypy reports zero issues.
- [ ] All automated tests pass.

Last verified M9 baseline: 89 tests passed.

## 3. CLI Features

- [ ] `sitepulse version`
- [ ] `sitepulse doctor`
- [ ] `sitepulse add`
- [ ] `sitepulse list`
- [ ] `sitepulse enable`
- [ ] `sitepulse disable`
- [ ] `sitepulse remove`
- [ ] `sitepulse check`
- [ ] `sitepulse monitor`
- [ ] `sitepulse history`
- [ ] `sitepulse report`
- [ ] `sitepulse config show`
- [ ] `sitepulse config set`
- [ ] `sitepulse config reset --force`

Use a disposable database when testing destructive commands.

## 4. Storage and Reports

- [ ] Monitoring results persist in SQLite.
- [ ] Historical observations can be retrieved.
- [ ] Reports calculate statistics correctly.
- [ ] CSV export works.
- [ ] JSON export works.
- [ ] Existing database records remain intact.

## 5. Security and Reliability

- [ ] Invalid configuration is rejected.
- [ ] Configuration recovery works.
- [ ] Configuration backups are excluded from Git.
- [ ] Batch insert errors do not leave partial results.
- [ ] Test-generated logs use temporary directories.
- [ ] Rotating application logging works.
- [ ] Logs do not intentionally contain secret URL values.
- [ ] Ctrl+C stops continuous monitoring.
- [ ] No secrets or credentials appear in tracked files.

## 6. Documentation

- [ ] README matches implemented features.
- [ ] Installation instructions work.
- [ ] Usage examples match CLI options.
- [ ] Architecture documentation is accurate.
- [ ] Project limitations are documented.
- [ ] LICENSE is present and appropriate.

## 7. GitHub

- [ ] `.gitignore` excludes generated files.
- [ ] Local SQLite databases are not committed.
- [ ] Local JSON configuration is not committed.
- [ ] Generated logs and reports are not committed.
- [ ] Recovery-test artifacts are excluded.
- [ ] Git working tree is clean after commit.
- [ ] Main branch is pushed to GitHub.

## 8. Optional Visual Presentation

- [ ] Screenshot of `sitepulse --help`
- [ ] Screenshot of monitoring dashboard
- [ ] Screenshot of history and statistics
- [ ] Screenshot of configuration output

Screenshots must contain no secrets, passwords, or sensitive URLs.

## 9. Release

- [ ] Final tests pass.
- [ ] Final commit is pushed.
- [ ] Release tag matches project version.
- [ ] GitHub release description is prepared.
- [ ] Release is created successfully.

Do not mark the release complete until these checks are verified.
