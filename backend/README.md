# AEGIS backend — Person 1

AEGIS is an operational pre-trade risk-checking and self-monitoring service for other trading-agent developers. The working FastAPI/SQLite backend includes actual official OKX Agent Trade Kit observations, an autonomous reference cycle, deterministic vetoes and typed model adapters. Person 1 owns this folder, `../contracts/`, `../docs/atk/` and `../docs/product/`. Dashboard, LAYA training and Fuji registration/receipts remain with their owners.

The authorized jury amendment adds `GET /api/v1/service` and `POST /api/v1/risk/evaluate` with a separate assessment-only credential. The initial v2 contract is frozen byte-for-byte; `contracts/service-openapi.yaml` contains the additive schemas. The assessment fetches server-side public ATK facts, never trusts caller account flags and never grants execution authority. See [service/customer/pricing guide](../docs/product/service.md), [two-minute demo](../docs/product/demo-2-minutes.md), [current status](../docs/product/STATUS.md), and [Person 3 handoff](../docs/product/person3-handoff.md).

Service 1.1 adds the requested string-notional form `{request_id,symbol,proposed_action,proposed_notional,requester_context?}` while preserving the previous quantity form. Its advisory response has `execution_authorized=false`, UNAVAILABLE/BLOCK when account facts are unknown/unsafe, reason/evidence IDs, evaluation time, mode, policy version and a null chain receipt. Request context is null-safe and ignored, never forwarded or audited; credential/private-balance content is rejected without echo. Effective-intent correlation is persisted and idempotent across restarts; changed intent under an existing ID returns 409. Historical replay does not promise current freshness.

## Reproducible standalone MOCK acceptance

```sh
cd backend
uv sync --python 3.12 --frozen
uv run python -m scripts.init_local
uv run python -m scripts.run_mock --port 8001
```

In another terminal, from `backend/`:

```sh
curl --fail-with-body --silent --show-error \
  --config data/mock-service.curl \
  --header 'Content-Type: application/json' \
  --data-binary @../contracts/fixtures/risk-notional-mock.request.json \
  http://127.0.0.1:8001/api/v1/risk/evaluate
uv run python -m scripts.prove_mock_contract --port 8001
```

Startup creates an ignored mode-0600 curl credential file, keeps real execution disabled, and uses a separate SQLite DB. Start triggers the configured MOCK NO_TRADE cycle without per-step prompts. The proof checks health, the full normalized phase timeline, HALT, idempotent Stop, assessment replay/conflict and actual SSE. The new notional MOCK route and autonomous MOCK cycle make no real integration calls. The legacy quantity form retains its real-public-market observer for compatibility; use the new form for the standalone MOCK demo. Source mode cannot be set by requester context.

Existing event types and Event/Decision fields remain unchanged. Normalized states are only in `Event.details.phase`, with `details.cycle_id`: OBSERVE → CLASSIFY → REASON → RISK_CHECK → ACT/NO_TRADE → VERIFY → AUDIT. `RISK_GATE` and `EXECUTE` retain their original type strings. `AEGIS_CYCLE_TIMEOUT_SECONDS` bounds the entire cycle (default 180 seconds); timeout stops new work and keeps uncertain submissions UNKNOWN. Stop is latched/idempotent until Start, and drains/cancels according to that bound rather than retrying an uncertain order.

The exact Person 3 schema bundle is [contracts/PERSON3_HANDOFF.md](../contracts/PERSON3_HANDOFF.md), with a frozen combined OpenAPI snapshot, hashes and captured example fixtures. Product positioning and the unvalidated 30-day experiment are in [ONE_PAGER.md](../docs/product/ONE_PAGER.md).

## Run locally

Python 3.11+ (tested with 3.12.13), Node 18+ with `--import` support (tested with 24.13.1), and uv/npm:

```sh
cd backend
uv sync --python 3.12 --frozen
npm ci --ignore-scripts --no-audit --no-fund
uv run python -m scripts.init_local
uv run uvicorn aegis.app:app --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

Open [API docs](http://127.0.0.1:8000/docs) and [snapshot](http://127.0.0.1:8000/api/snapshot). `init_local` creates a mode-0600, git-ignored `.env` with a random local control token and preserves existing configuration. Never commit it. No trading keys are included. The default is MARKET_ONLY, stopped until an authenticated start request. CLI/MCP packages are pinned to official 1.4.8; actual calls use the CLI subprocess, with no Python direct-OKX-REST substitute. MCP is installed for interoperability but is not the transport claimed by this implementation.

To start without displaying the token:

```sh
uv run python - <<'PY'
import httpx
from aegis.settings import Settings
s = Settings()
with httpx.Client(trust_env=False) as c:
    r = c.post('http://127.0.0.1:8000/api/agent/start',
        headers={'Authorization': 'Bearer ' + s.control_token.get_secret_value()})
    r.raise_for_status()
    print(r.json())
PY
```

Use the same request with `/api/agent/stop` to stop. Stop latches execution off until the next start, and waits for bounded in-flight work instead of blindly canceling a submission. Run a single Uvicorn worker; local cycle/lifecycle state is process-owned. SQLite independently serializes intent claims across connections.

## What runs

`observe → classify → reason → deterministic policy → NO_TRADE or bounded demo IOC → reconcile → audit` runs autonomously every configured interval. ATK preserves exchange timestamps. Missing/invalid LAYA gives REVIEW + abstention; missing/invalid EVREN gives NO_TRADE. Every stage emits persisted events. A missing observation is audited as NO_TRADE. Model integrations never receive credentials, control tokens, executable tools or override authority.

Three explicit modes:

| Mode | Observation/models | Execution |
|---|---|---|
| MARKET_ONLY (default) | Real ATK market; configured model services or explicit fallbacks | Always NOT_SENT |
| MOCK | Scripted market, operational labels and proposals, all marked MOCK | Local simulation, `MOCK_FILLED`, always NOT_SENT |
| OKX_DEMO | Real ATK market/account and configured model services | Disabled unless all local demo interlocks and policy checks pass |

To demonstrate safely without integrations, set `AEGIS_SOURCE_MODE=MOCK` locally, restart the server, and POST `/api/demo/scenario` with a supported scenario and the control token. Scenarios: `normal`, `stale_feed`, `laya_halt`, `excess_exposure`, `invalid_quantity`, `missing_approval`, `unknown_order`, `duplicate_intent`. Repeating `duplicate_intent` is vetoed after its first approved simulation. The default autonomous MOCK cycle is deliberately scripted; it is not evidence of trained model performance. [Shared contract details](../contracts/README.md).

## Deterministic policy and journal

Only BTC-USDT cash spot is allowed. No leverage, derivatives, withdrawals or live-mode branch. Fixed limits: at most 25 quote units per order with 1% fee headroom, at most 1,000 total marked non-USDT exposure, feed/account age at most 15 seconds and future tolerance 2 seconds. Account level 1 (cash) and no liabilities are required. Tick-aligned IOC limit orders bind the approved execution price, using a 1% adverse-price allowance; no uncapped market orders. Fees beyond the reserved allowance are not independently benchmarked, and no successful demo fill is claimed.

Stale/future data, invalid min/lot sizes, crossed quotes, unknown account, insufficient available balances, excess exposure, external pending orders, internal PENDING/UNKNOWN order, duplicate intent, non-CONTINUE/low-confidence/abstaining LAYA, missing approval or stop latch veto new submissions. CONTINUE is never permission by itself. LLM output is strict typed JSON; extra tool/override fields, tool calls, nonfinite numbers and unsupported symbols are rejected. HTTP model responses have a 15-second total request deadline and 256 KiB byte limit; generation requests cap output at 600 tokens and disable EVREN server tools.

SQLite commits the PENDING intent and initial decision before submission. `clOrdId` is a server-generated 32-character ID. Ambiguous submission is reconciled by that ID, never retried as a new placement. UNKNOWN blocks further orders across restarts. Final journal and decision status commit atomically; rejected duplicate decisions cannot overwrite the original intent. Read-back matches symbol, client ID, side, quantity, IOC type, cash mode and approved price. VERIFIED means terminal venue state was independently read, including canceled; it does not guarantee a fill or profits. Failures that cannot establish a terminal venue state conservatively remain UNKNOWN.

ATK runs in an isolated temporary profile/OAuth/log directory, with an allowlisted child environment and forced `--demo`/regional site. Personal `~/.okx` configuration, inherited live keys, proxy/base-URL overrides and unrelated secrets are excluded. Raw child stderr and arbitrary provider exceptions are not published. Persisted/public audit fields redact configured secrets. Private API credentials go only to the isolated ATK child environment; never to command-line arguments or the dashboard.

## Connect EVREN later

The provided EVREN URL and its public OpenAPI were actually inspected. Put `AEGIS_EVREN_API_KEY=...` in local `.env`; use the EVREN UI to review/accept its current terms. The runtime checks `GET /v1/terms/status` (`accepted: true`, `current_version`) and never accepts terms automatically. It sends `X-API-Key`, matching the supplied instructions.

```sh
uv run python -m scripts.discover_evren
```

Copy an actual returned account model ID into `AEGIS_EVREN_MODEL`, then restart. If exactly one model is returned, the client can select it automatically; multiple models require an explicit discovered ID. Names from examples are never assumed. Each cycle discovers the account's current models before requesting a bounded, nonstreaming `/v1/chat/completions` proposal. Authenticated discovery/generation is NOT_TESTED until a local key is configured; public schema retrieval and HTTP 401 are not model-integration proof.

## Connect LAYA later

Set `AEGIS_LAYA_URL=http://<RTX-LAN-IP>:<port>` and optional `AEGIS_LAYA_TOKEN`. The client calls `/classify` using the shared contract. Model training, actual VRAM measurement via `nvidia-smi`, and benchmark publication are Person 2's tasks. An adapter PASS proves a schema-valid response only, not fine-tuning quality. Until connected, status remains NOT_TESTED and operational output is explicitly `advisory-fallback`, REVIEW/abstained. No model is deployed to the EVM.

## Demo execution interlocks

Actual demo execution is NOT_TESTED. Keep the current read-only mode until an isolated DEMO account is available. The server requires `source_mode=OKX_DEMO`, `AEGIS_DEMO_ENABLED=true`, `AEGIS_DEMO_REGION_CONFIRMED=true`, all three isolated `AEGIS_OKX_DEMO_*` values, permitted account read-back, and every deterministic check. The region confirmation is an explicit operator attestation after checking official regional demo support; it is not inferred from a public ticker. TR accounts must use `AEGIS_OKX_SITE=tr`. Read + Trade permissions only; any Withdraw permission blocks account readiness. Keys must actually be DEMO keys: the forced simulated header does not manufacture credentials or regional support.

If TR demo cannot be confirmed, continue real MARKET_ONLY observations and show the separately labeled MOCK flow. No public control endpoint should be exposed without authentication. Keep control secrets in a private Next.js server proxy, never a client bundle. No live orders were placed during development or proof capture.

## Verify and reproduce evidence

```sh
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run python -m scripts.export_contract --check
uv run python -m scripts.prove
# With the MARKET_ONLY HTTP server running:
uv run python -m scripts.http_smoke
```

`scripts.prove` forces MARKET_ONLY for real ATK and a separate temporary MOCK runtime. It performs no exchange writes, ignores local model credentials, and saves actual events, timestamps, decisions and capability results. `http_smoke` tests the real local server, authorization, autonomous ATK observation, mode isolation and SSE resume, then leaves the agent stopped. The HTTP server remains available for inspection. Inspect [evidence/latest.json](evidence/latest.json), [evidence/http-smoke.json](evidence/http-smoke.json), and [evidence matrix](evidence/MATRIX.md). Unit tests use explicit fake transports/venues; those successes do not certify real model or demo integration.

Remaining dependencies: EVREN local key/terms/model selection, RTX LAN LAYA URL and benchmark, isolated demo credentials/regional confirmation, and Person 3's independently verified Fuji identity. `/api/web3/identity` intentionally remains unverified/null. Do not describe the runtime as on-chain, a successful demo trade, profitable or fully integrated. No organizer bonus is claimed.
