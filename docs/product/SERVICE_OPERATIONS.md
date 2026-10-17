# Service API, protected deployment and one-week pilot

**Actual state:** local backend and dashboard work; official ATK public reads, EVREN proposal, LAN LAYA advisory/fallback and Fuji identity/receipt are evidenced. A restricted backend is temporarily reachable over Cloudflare Quick Tunnel; no permanent backend host or public dashboard is deployed. Public Gist metadata and Fuji contracts remain separate artifacts. No marketplace listing, customers, payments or revenue are claimed.

## Contract and executable local request

OpenAPI: `contracts/service-openapi.yaml`; exact frozen bundle/fixtures: `contracts/PERSON3_HANDOFF.md`, `contracts/fixtures/`. GET `/api/v1/service` describes the API. POST `/api/v1/risk/evaluate` accepts:

```json
{"request_id":"pilot-example-001","symbol":"BTC-USDT","proposed_action":"BUY","proposed_notional":"10","requester_context":null}
```

Notional is quote USDT as a Decimal string, not a JSON float. Optional context is untrusted, ignored and not forwarded to models or written into audit events. Credential/private-balance fields are rejected without echo. No exchange credentials, account balances or order IDs belong in public input.

Run this actual curl from `backend/` after starting the server. The helper supplies the configured service key through curl stdin rather than argv/history; it never prints the key:

```sh
uv run python - <<'PY'
import json, subprocess
from aegis.settings import Settings
s=Settings(); assert s.service_api_key
body=json.dumps({"request_id":"pilot-example-001","symbol":"BTC-USDT","proposed_action":"BUY","proposed_notional":"10","requester_context":None})
subprocess.run(['curl','--fail-with-body','--silent','--show-error','--config','-',
  '--header','Content-Type: application/json','--data-binary',body,
  'http://127.0.0.1:8000/api/v1/risk/evaluate'],
  input='header = "X-AEGIS-Key: '+s.service_api_key.get_secret_value()+'"\n',text=True,check=True)
PY
```

Nine response fields: `request_id`, `verdict`, `execution_authorized`, `reason_codes`, `evidence_ids`, `evaluated_at`, `source_mode`, `policy_version`, `chain_receipt`. Verdict is ALLOW_FOR_FURTHER_CHECKS/BLOCK/REVIEW/UNAVAILABLE; `execution_authorized` is always false. A small real-market request currently returns UNAVAILABLE because trusted account facts are absent; an unsafe request returns BLOCK. `chain_receipt=null` means this particular assessment has no verified chain receipt. The already anchored sample must not be attached to unrelated evaluations.

The MARKET_ONLY notional path now invokes the same `aegis.policy.check` used by the autonomous agent. It discards any accidental operator-account data, derives a lot-aligned assessment-only quantity using public prices and checks freshness, precision, instrument state, quote consistency and sizing. It does not return an executable order size. Zero placeholders are not verified balances or exposure findings. The notional API does not buy an LLM call: `MODEL_ANALYSIS_NOT_REQUESTED` is explicit. The preserved legacy quantity form includes bounded EVREN/LAYA analysis. Neither form trades.

Identical effective intent/ID replays its original timestamped response. A changed intent under the same ID returns 409. Internal policy-implementation revision separates new gate-backed cache entries from older implementation results. Historical replay is not a new market observation. The public response/OpenAPI shape remains unchanged.

## Implemented access, limits and retention

The assessment credential is separate from the operator control credential. Missing configuration returns 503, invalid/missing key 401, malformed input 422, oversized body 413, conflict 409 and rate/concurrency limits 429 with Retry-After. The body cap is 2,048 bytes with a five-second read deadline. Default assessment budget is 30 seconds; the ATK subprocess boundary remains bounded. Quotas are one worker, six admitted evaluations/minute and one concurrent assessment; they reset at process restart and are not tenant billing.

SQLite on the operator/server disk persists sanitized events, effective symbol/action/notional, reason codes, public market provenance/hashes/timestamps and cached responses. Requester context is not retained. Raw private provider responses/stderr, credentials and hidden model reasoning are withheld; configured secrets are redacted. Run/request IDs should be random correlation strings, never personal identifiers. Model state excludes credentials and account/order IDs; correlation IDs remain transport metadata for LAYA.

**Current retention is indefinite until operator deletion**; no automatic TTL, encryption-at-rest layer, multi-tenant isolation or deletion portal is implemented. SQLite/WAL/backups need host access controls and encrypted storage. For a consenting pilot, agree a seven-day retention window, export the agreed redacted aggregate, then have the operator delete the dedicated pilot database/WAL/backups. This is a proposed operating procedure, not an implemented purge guarantee. Public chain/Gist publications cannot be represented as private or automatically erasable. No customer data has been onboarded by this experiment.

## Install and deploy safely

Local, measured entrypoint:

```sh
cd backend
uv sync --python 3.12 --frozen
npm ci --ignore-scripts --no-audit --no-fund
uv run python -m scripts.init_local
uv run uvicorn aegis.app:app --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

Set optional EVREN/LAYA URLs/model version only in the ignored mode-0600 environment file. Keep MARKET_ONLY and both demo flags false. The API runs without model availability via explicit fail-closed fallbacks. The official ATK packages remain pinned in `backend/package-lock.json`. No direct exchange REST substitute is used.

For a future public service, use the tested restricted entrypoint on a separate server/database, not the operator app:

```sh
uv run uvicorn aegis.public_app:app --host 127.0.0.1 --port 8002 --workers 1 --no-access-log
```

It forwards only GET health, GET service descriptor and authenticated POST assessment. It rejects demo configuration and returns 404 for controls, events, snapshot, tools, docs and other paths, even with a valid operator token. Place TLS/edge abuse limits in front of it; `deploy/Caddyfile.example` is a not-deployed example based on [Caddy reverse proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy) and [path matchers](https://caddyserver.com/docs/caddyfile/matchers). Run `caddy validate --config deploy/Caddyfile.example --adapter caddyfile` after installing Caddy and supplying an actual owned DNS name. Caddy/TLS deployment has not been executed here. Maintain a persistent private SQLite volume and one worker; configure backup/restore before hosting.

Public frontend option: build the existing Next application on a host with Node 24 and the whole repo's public proof artifacts, `npm ci`, `npm run build`, `npm start -- --hostname 127.0.0.1`. Keep AEGIS_DASHBOARD_ADMIN_SECRET and AEGIS_CONTROL_TOKEN absent in a public judge deployment. The BFF then cannot forward Start/Stop/scenario mutations. A protected operator dashboard is a separate local/private deployment. Recorded examples are labeled RECORDED_PROOF, never new live evaluations. Do not expose private ATK MCP, provider credentials or exchange/account endpoints. No NEXT_PUBLIC secret is supported.

After obtaining a host, test actual public HTTPS health from a second machine, authenticated evaluation and missing-auth denial, 404 control paths and body/rate limits. Only then record the real URLs in the deployment manifest and propose the ERC-8004 service reference. The temporary HTTPS checks below passed from the operator client; a second-device check and permanent deployment remain NOT_TESTED.

## Buyer, economics and seven-day pilot hypothesis

ICP: a 2–10-person engineering team operating spot trading agents or an agent platform, with repeated retries, stale-input incidents or audit gaps. Buyer is the technical founder/platform lead; users are agent/backend developers. AEGIS complements exchange validation with cross-cycle uncertainty, idempotency and attributable policy receipts. Current differentiation is architectural/tested behavior, not proven avoided losses or model superiority.

Hypotheses: USD 0.01/evaluation or USD 99/team/month with 10,000 evaluations. No payment/subscription implementation or revenue. Validate cost per check and support burden before committing to either price; enriched AI analysis is a separate cost center. Market checks are seconds-scale, not HFT. No named customer or willingness-to-pay result is fabricated.

| Pilot day | Proposed activity | Evidence / decision |
|---|---|---|
| 1 | Recruit up to five consenting target teams for problem interviews | Record actual counts, including zero; no implied clients |
| 2 | Give interested teams the schema, key and isolated sandbox | Measure integration time and authentication failures |
| 3 | Replay labeled synthetic stale, duplicate and ambiguous-submit incidents | Confirm no execution and understandable reasons; preserve source/derivative groups |
| 4 | Shadow real public market requests; keep account data unknown | Measure real availability, provenance coverage and p50/p95 latency |
| 5 | Review false blocks/missing-context cases with developers | Do not relabel data or relax vetos to improve the demo |
| 6 | Compare per-call and team-tier offers | Record actual expressed interest; no revenue claim |
| 7 | Export agreed anonymized outcomes, review costs and retention | Continue only with repeat use, useful reasons and plausible unit economics; otherwise stop or revise |

## Actual temporary HTTPS demonstration

On 2026-10-17 the restricted entrypoint at local port 8002 was exposed at `https://tears-forms-inexpensive-geometry.trycloudflare.com`. Evidence: `backend/evidence/public-service-http.json`. GET health/descriptor returned 200; keyed evaluation returned 200/UNAVAILABLE with actual ATK provenance; no key returned 401; controls and private data returned 404. The service key was never published. The operator HTTPS client performed these checks; a second-device independent check is NOT_TESTED (web fetch tool could not access this domain).

This address lasts only while the tunnel/process runs; no SLA, durable DNS, uptime or production deployment is claimed. [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/) are for testing and do not support SSE. The verified official darwin-arm64 release was 2026.10.1, archive SHA256 `647615df99d49cd179ea5e13ef760b9bbfb33630f6ae62f87e33dfadda60adcc`. Reproduce with `cloudflared tunnel --url http://127.0.0.1:8002` after starting the restricted service; a new invocation produces a different hostname. Never tunnel operator port 8000 or publish dashboard administration secrets.

The local dashboard bridge gives the bounded backend assessment up to 40 seconds and displays HTTP/conflict/rate-limit errors. Null/array/scalar bodies are rejected before a provider call. `backend/evidence/risk-service-bff.json` records actual authenticated calls through the frontend, distinct from view-only recorded fixtures.
