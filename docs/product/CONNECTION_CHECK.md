> Historical connection report from 12:25 UTC. Superseded for current status by `backend/evidence/system-status-http.json`, `exchange-readiness.json`, `models.json` and `docs/JURY_EVIDENCE.md`. The LAYA-unconfigured statements below describe that earlier probe only. EVREN feature probes are time-dependent; do not infer current PASS from this historical table.

# Provider connection check — 2026-10-17

LAYA LAN integration is the next implementation step. It is currently **NOT_TESTED / NOT_CONFIGURED** and execution remains blocked. No `ml/**` files were changed.

| Check | Actual result | Evidence |
|---|---|---|
| Authenticated EVREN terms/model discovery | PASS | `backend/evidence/models.json` |
| `deepseek-v4.1-flash` structured JSON probe | PASS | `backend/evidence/models.json` |
| Separate no-op tool-calling probe | PASS; returned tool was never executed | `backend/evidence/models.json` |
| Real ATK public MCP market observation → schema-validated EVREN proposal → NO_TRADE | PASS | `backend/evidence/provider-live-smoke.json` |
| Actual frontend BFF Start → FastAPI autonomous cycle → deterministic stop | PASS; NO_TRADE / NOT_SENT | `backend/evidence/provider-http-smoke.json` |
| Official CLI forced-demo TR config, balance and BTC-USDT open-order reads | PASS; reported environment `demo`, Read + Trade, no Withdraw | `backend/evidence/provider-demo-preflight.json` |
| Demo order submission / reconciliation | NOT_TESTED; no exchange writes | Same preflight report |
| Injected MOCK stale feed / duplicate intent | PASS; separate synthetic HALT scenarios | `backend/evidence/provider-live-smoke.json` |
| Recorded replay integrity and frozen API contract | PASS | Commands below |

The HTTP run ID is `3f341ffad8ea45a191b7ab18e0d2e160`. Public ATK/MCP and model tool-call events, correlation IDs, measured timings and response hashes are in the evidence files. Upstream HTTP status is UNKNOWN where the official CLI/MCP does not expose it. Raw account payloads and credentials are excluded.

The diagnostic report's generic `EVREN` status remains NOT_TESTED because its two capability probes do not invoke the production proposal path. The separate autonomous and HTTP evidence files record production `EVREN=PASS`. Neither probe behavior nor a successful account read grants execution permission.

Local EVREN model selection uses an ID returned by authenticated account discovery. Settings and credentials remain in ignored `backend/.env` with mode 0600. Existing dashboard/backend authentication tokens were restored from the matching local dashboard configuration after the environment file was replaced. Persistent demo execution flags were not enabled by these probes. The agent is stopped after the bounded HTTP test; the web servers remain available.

Executed commands from `backend/`:

```sh
uv run python -m scripts.discover_evren
uv run python -m scripts.verify_models --evren-features
uv run python -m scripts.prove_model_safety --output evidence/provider-live-smoke.json
uv run python -m scripts.prove_model_safety --replay evidence/provider-live-smoke.json
uv run python -m scripts.export_contract --check
```

Installed `okx --help`, `okx-trade-mcp --help`, `okx account config --help`, `okx account balance --help` and `okx spot orders --help` were checked. Additional bounded local probes used argv-list subprocesses with the pinned official CLI, isolated profiles, local credentials, `--site tr --demo --json --env`, and these read-only operations: `account config`, `account balance`, `spot orders --instId BTC-USDT`. They never invoked an order-writing operation or direct exchange REST. Routing and demo settings follow the [official configuration documentation](https://github.com/okx/agent-trade-kit/blob/github-main/docs/configuration.md).

Next: obtain Person 2's LAYA LAN base URL, returned `model_version` and optional local token; run `uv run python -m scripts.verify_models --laya`, then repeat the bounded autonomous/HTTP test. No demo-order test is claimed or enabled here.

Current measured refresh: LAYA LAN transport/version PASS with REVIEW/abstained=true. Forced-demo account read PASS with no submission. Latest EVREN feature check: discovery PASS, structured output FAIL at a 15-second timeout, separate tool calling PASS; see current `models.json` and preserved `models-feature-timeouts.json`. A prior successful NO_TRADE production cycle is separately evidenced, not proof of uninterrupted provider availability.
