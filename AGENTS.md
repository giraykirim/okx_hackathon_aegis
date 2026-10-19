# AEGIS development instructions

## Scope and ownership
- Work from this repository root. Person 1: `backend/` and `contracts/`; Person 2: `ml/`, `models/`, `data/`, `scripts/ml/`; Person 3: `frontend/`, `web3/`, deployment and pitch material.
- Give each task one concrete outcome and a list of allowed file groups. Carry out work already authorized by the user without repeatedly requesting the same approval.
- Read narrower `AGENTS.md` files before editing their directories. For Next.js, the frontend instructions point to the installed version's local documentation.

## Start once, then use the same tools
- `python scripts/dev.py doctor` checks Python/Node/Git/ripgrep and local test dependencies without network access or installs.
- Backend Python is `backend/.venv`; ML prefers `AEGIS_ML_PYTHON`, then `.venv-ml`, then the existing sibling `../aegis/.venv`. Never recreate environments or download model weights merely to inspect the project.
- `python scripts/dev.py test --suite backend --target tests/test_policy.py`
- `python scripts/dev.py test --suite ml --target test_dataset.py`
- `python scripts/dev.py test --suite frontend --target src/__tests__/truthfulness.test.ts`
- `python scripts/dev.py test --suite web3`
- `python scripts/dev.py test --suite tooling`
- `python scripts/dev.py test --suite all` is the final full verification, not the first debugging step.
- The runner executes Node directly, merges stdout/stderr into full logs, and propagates the child exit code. Reports are in ignored `.devtools/runs/`. Read the first full failure log; do not repeatedly rerun a whole suite to recover truncated output.

## Preserve evidence and boundaries
- Never normalize line endings across the repository. `.gitattributes` deliberately contains mixed LF/CRLF rules for existing SHA-256-pinned files.
- `python scripts/dev.py integrity` compares explicitly pinned working files with Git's HEAD checkout filters; it reports differences and does not rewrite them or validate every historical manifest.
- Do not rewrite `data/`, `models/`, frozen contract files, published metadata, or their manifests just to make tests green. First identify the exact file, authoritative digest, encoding/BOM, and required line ending.
- Do not read, print, commit or send `.env` values, API keys or operator credentials. Offline unit tests do not require live services or account access.
- Live orders, network proof scripts, deployment and new training runs are separate work scopes. Do not invoke them as a side effect of unit verification.
- Avoid `git add -A`, forced checkout and automatic commits for routine fixes. Review the exact diff and preserve unrelated user changes.

## Keep tasks efficient
- Prefer focused searches in source directories; exclude dependency trees, weights and historical evidence unless the task needs them.
- Batch independent reads. Use a single diagnostic report instead of many tiny model/tool turns.
- Run the failed test first, its suite next, and the complete verification after the final change. Repeat only for new changes or unresolved failures.
- At a task boundary, leave a short handoff with outcome, changed files, exact checks, unresolved issues and next action. Start the next independent task in a fresh session instead of replaying the whole historical chat.
- A passing unit suite is not evidence of live exchange execution, deployment, public listing or model training.
