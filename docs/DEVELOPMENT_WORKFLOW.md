# Daily development

Run commands from the project root with Python 3.11 or newer. No OpenCode plugin is required for these checks.

```powershell
python scripts/dev.py doctor
python scripts/dev.py test --suite backend --target tests/test_policy.py
python scripts/dev.py test --suite ml --target test_dataset.py
python scripts/dev.py test --suite frontend --target src/__tests__/truthfulness.test.ts
python scripts/dev.py test --suite web3
python scripts/dev.py test --suite tooling
python scripts/dev.py test --suite all
python scripts/dev.py integrity
```

`doctor` checks local executables and required modules, without installing packages, reading credential files, calling services, or loading model weights. Set `AEGIS_ML_PYTHON` if the ML environment is in a different location. The existing sibling `../aegis/.venv` remains a compatibility fallback.

`test` calls the Python or Node executable directly, without shell pipelines. All child stdout/stderr goes to a complete log. A failing child produces a failing runner exit code. Missing tooling is an explicit setup failure; timeouts are reported as 124. Reports, commands, durations and exit codes are written to ignored `.devtools/runs/<run>/summary.json`. It does not install dependencies or start application servers. Operator/provider credential variables are removed from the child environment.

Start with the relevant test. Read its full log if it fails. Run all suites after the final fix. `--target` selects pytest paths, one ML discovery pattern, or Vitest files; it cannot be used with `--suite all`.

`integrity` is read-only. It compares explicitly EOL-pinned paths to Git's HEAD checkout output and reports changed bytes. A legitimate edit to a pinned file will therefore be reported too. It neither changes line endings nor re-signs historical manifests. Preserve frozen evidence; a coordinated versioned migration is a separate task.

For installs, use the project's lockfiles and `npm.cmd` on Windows, separately from tests. The test runner does not need npm because it invokes local Vitest through Node. The existing `backend/scripts/jury_check.ps1` remains a service-dependent evidence procedure, not the daily offline check.

Before the next independent OpenCode task, use a short handoff:

```text
Outcome:
Allowed directories:
Files changed:
Checks and report path:
Remaining issue:
Next action:
```
