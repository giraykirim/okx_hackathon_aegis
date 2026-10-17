# AEGIS shared API v2

Person 1 owns the contracts. `openapi.yaml` is the frozen initial v2 artifact (SHA-256 `a437caaa81ae590fc258aa0aeeb6498b1c38ec745483a701a4b2f0c66314d5ae`); all eleven existing routes and their schemas remain unchanged. The authorized amendment adds two routes in `service-openapi.yaml`, with no change to the frozen file. The runtime `/openapi.json` includes both. Person 3 coordination is recorded in `docs/product/person3-handoff.md`; no acknowledgment is assumed.

Export the additive contract / check both from `backend/` (never rewrites frozen v2):

```sh
uv run python -m scripts.export_contract
uv run python -m scripts.export_contract --check
```

The additional `GET /api/v1/service` returns public metadata, proposed unbilled pricing, NOT_LISTED status and no invented public origin. `POST /api/v1/risk/evaluate` requires the separate `X-AEGIS-Key`; it accepts only symbol/side/quantity/optional correlation ID. Market facts come from a separate server ATK observer, and caller account facts remain unavailable. Response is REVIEW/HALT, with order_permission=false, execution_authority=false, provenance, model availability and a documented assessment hash. Assessments appear as SERVICE_ASSESSMENT events, never trading Decisions or order intents. See `docs/product/service.md` for input/output, real curl usage and implemented access/body/rate/deadline limits.

Events are returned oldest-first within the latest `limit` (1–1000, default 100). Decisions are newest-first (1–500, default 50). `/api/stream` emits `event: aegis`, with the complete Event JSON in `data`, persistent event ID in `id`, and heartbeat comments. Send `Last-Event-ID` to resume; an unknown cursor replays retained events. Initial connections replay the latest 100 events. No invented timeline entries or browser-generated metrics.

`POST /api/agent/start` and `/stop` accept no body and require `Authorization: Bearer <local control token>`. `/api/demo/scenario` takes `{"scenario":"stale_feed"}` with the same authentication. Supported scenarios are enumerated in OpenAPI, and only MOCK allows them. Missing server token disables all mutations (503); invalid credentials return 401; scenarios outside MOCK return 409. Start is idempotent. Stop prevents new submissions and drains bounded operations/reconciliation already in flight. A new start releases the stop latch.

Use a Next.js server-side proxy for dashboard control actions; keep the backend token in private server environment, never `NEXT_PUBLIC_*`. Default backend binding is loopback. Public deployments need an authenticated proxy; do not expose control routes directly. Read-only endpoints require no token. No cross-origin CORS permissions are enabled by default.

Source modes are `MOCK`, `MARKET_ONLY`, `OKX_DEMO`. Statuses are `NOT_SENT`, `PENDING`, `VERIFIED`, `FAILED`, `UNKNOWN`. In MOCK, an approved scripted action records `venue_state=MOCK_FILLED` with `execution_status=NOT_SENT`, no venue order ID. It never becomes exchange VERIFIED. In OKX_DEMO, VERIFIED means an independent exchange read matched the persisted cash IOC order and reported a terminal state; a canceled order can be verified without being filled. Display `venue_state` alongside status. No profit claim follows from verification.

Decision extensions beyond the mandatory brief fields: `intent_id`, `quantity` (base BTC decimal string), `venue_state`, and `limit_price` (policy price cap/floor, decimal string or null). These fields support durable idempotency and price-bounded execution. Price and cash IOC mode are checked during read-back. Observation extensions include exchange timestamp, tick/lot/min sizes, account timestamp, account-known flag, available amounts and external-order flag. Unavailable account figures remain placeholders with `account_known=false`; render them as unavailable, not real zero balances.

Capabilities use `ATK_MARKET`, `ATK_ACCOUNT`, `ATK_DEMO`, `EVREN`, `LAYA`, `ERC8004`, each with PASS/FAIL/NOT_TESTED, evidence strings and checked time. PASS means the specific adapter response was observed and validated, not that a model was independently benchmarked. MOCK does not mark external integrations PASS. Metrics are audit-derived counts; `pnl=null` is unavailable.

Identity deliberately returns chain 43113 with null addresses, IDs, hashes and `verified=false`, `verification_status=NOT_TESTED`. It includes both `registration_tx_hash` and `tx_hash` for the two field spellings in the brief. Person 3 must coordinate an implementation that independently reads the Fuji registry's owner/agentURI and transaction receipt before changing this response. A local metadata file alone must never enable `verified`. Registration identifies an off-chain runtime; Python and LAYA do not execute on the EVM.

Person 2's LAN interface remains `POST /classify` with `{state,run_id,correlation_id}` and `{label,confidence,abstained,model_version,latency_ms}`. State is the Observation schema here. Labels are operational CONTINUE/REVIEW/HALT; confidence is finite 0–1. The backend uses REVIEW/abstained on missing, timed-out, oversized or invalid responses.
