# AEGIS Risk Check Service

Current service version is 1.1.0. The recommended contract is now `{request_id,symbol,proposed_action,proposed_notional,requester_context?}`; decimal notional is a quote-USDT string. It returns `{request_id,verdict,execution_authorized:false,reason_codes,evidence_ids,evaluated_at,source_mode,policy_version,chain_receipt}`. Context is untrusted, ignored and never logged/forwarded. No path returns ALLOW while trustworthy account data is unavailable. UNAVAILABLE and hard-policy BLOCK are explicit. Chain receipt is null. See [current frozen handoff](../../contracts/PERSON3_HANDOFF.md) and [fixtures with actual cURL](../../contracts/fixtures/README.md).

`AEGIS_SERVICE_SOURCE_MODE` is selected by the server for this new form: MOCK is deterministic, makes no external calls and declares real data unavailable; MARKET_ONLY fetches real public ATK data but still withholds account approval. Identical effective requests replay the original stored result across restart; changed intent with the same request ID conflicts. The prior `action`/base `quantity` form, described below, remains supported with its original richer assessment response and real-market observer. Do not mix fields from the two forms.

AEGIS checks operational pre-trade conditions for developers building trading agents. A target customer is a small agent-platform team that needs a consistent policy check, a reason it can act on, and evidence explaining which market facts the check used. The problem is accidental or unsupported execution when a model, stale feed, missing account state or uncertain prior order is treated as authority.

The prototype provides server-sourced BTC-USDT market/instrument checks, a deterministic sizing veto, declared LAYA/EVREN availability, and a hashable assessment. The autonomous reference agent demonstrates the same separation between models and execution policy. It is not an alpha signal, investment recommendation, delegated broker or guarantee that a later order is safe.

## Contract and real example

The original [v2 contract](../../contracts/openapi.yaml) is frozen. [service-openapi.yaml](../../contracts/service-openapi.yaml) adds only:

- `GET /api/v1/service`: public service/auth/limits/pricing/listing metadata. `public_url=null` until a verified deployment is coordinated.
- `POST /api/v1/risk/evaluate`: separately authenticated assessment. Input is only symbol, BUY/SELL, positive base-BTC quantity and optional client correlation ID. No balance, source-mode, market freshness, model label, remote URL, secret, tool or permission fields are accepted.

For a server-side consumer, load the **assessment-only** credential from a secret store into a local curl configuration; do not paste it into a browser, chat, shell history or client bundle. One local example that reads `.env` without displaying the key:

```sh
cd backend
uv run python - <<'PY'
import subprocess
from aegis.settings import Settings
s = Settings()
assert s.service_api_key
config = 'header = "X-AEGIS-Key: ' + s.service_api_key.get_secret_value() + '"\n'
subprocess.run(['curl', '--silent', '--show-error', '--fail-with-body',
    '--config', '-', 'http://127.0.0.1:8000/api/v1/risk/evaluate',
    '--header', 'Content-Type: application/json',
    '--data', '{"symbol":"BTC-USDT","action":"BUY","quantity":"1","client_request_id":"demo-oversize"}'],
    input=config, text=True, check=True)
PY
```

The localhost URL is the actual local deployment, not a public origin. The response contains assessment ID/run ID, timestamp, reasons, market provenance, exact ATK receipts, LAYA/EVREN status, limitations and `assessment_sha256`. A large intended order returns HALT with `excess_order_notional`. A small market-valid intent returns REVIEW while account context or models are missing. Market freshness can independently produce HALT. All outcomes have `execution_authority=false`, `order_permission=false`, and `account_provenance=UNAVAILABLE`. The service does not create a trading Decision, claim an intent, query the operator's private account or submit/reconcile an order.

The runtime fetches fresh public data through a separate credential-free ATK observer, even if the demo agent is configured with private credentials or MOCK inputs. Unknown account placeholders do not become insufficient-balance or exposure findings. In particular, this service cannot certify the caller's total exposure or unknown prior order state. A future account-connected tier requires a separate authenticated account binding and independent provenance review; caller flags cannot enable it.

## Access and limits implemented now

`X-AEGIS-Key` uses a separate local credential; it cannot start the autonomous loop or trade. Missing configuration returns 503; invalid keys return 401. `scripts.init_local` adds a random service credential to an existing local `.env` without replacing control keys. No key is included in public metadata or evidence.

The prototype permits one assessment at a time and six admitted assessments per rolling minute by default, with 429 and `Retry-After`. Limits are in-process for a single worker and reset at restart; they are not customer metering or a distributed quota. Request bodies, including chunked bodies and deployment prefixes, are capped at 2,048 bytes with a five-second body deadline. An assessment has a configurable total deadline of 30 seconds; model responses retain their own size/time limits. No external execution endpoint is exposed by this API.

Before publishing, put TLS and edge authentication/rate limiting in front of the service, issue/revoke distinct tenant credentials through a real identity system, and enforce distributed limits if scaling. Keep `/api/agent/*` and `/api/demo/*` private. Person 3 must provide the actual host/origin; no public deployment or URL is claimed here. The backend's local read-only proof is available now. No CORS origin is enabled implicitly.

## Commercial hypothesis, not billing

Proposed developer pricing: USD 0.01 per assessment; a USD 99/month B2B tier including 10,000 assessments, audit export and team integration support. Both are explicitly `PROPOSED_NOT_BILLED`; no subscription, payment rail, x402 claim, customer contract or revenue is implemented. Prices are hypotheses to validate with customers and real authenticated model costs. Heavy analysis may require a higher-priced tier after measuring token usage, latency and support cost. This is a seconds-scale operational service, not a low-latency execution feed.

The buyer's measurable value would be fewer invalid submissions and clearer incident reconstruction. Current proof establishes deterministic vetoes and attributable market observations. It does not establish loss reduction, profitability, market demand, trained-model superiority or production SLA.
