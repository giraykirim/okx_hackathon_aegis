# AEGIS — Frontend Dashboard & Server-Side API Bridge (`frontend/`)

Owned by **Person 3** (`frontend/**`, `web3/**`, `docs/pitch/**`).

## Architecture & Truthfulness Guarantees
- **Contract-First:** Consumes the frozen Shared API v2 ([`contracts/openapi.yaml`](../contracts/openapi.yaml), SHA-256 `a437caaa81ae590fc258aa0aeeb6498b1c38ec745483a701a4b2f0c66314d5ae`) and the additive B2B Risk Check Service contract ([`contracts/service-openapi.yaml`](../contracts/service-openapi.yaml)).
- **Zero Client Secrets:** No `NEXT_PUBLIC_*` secret variables or `localStorage` tokens exist. All operator mutations (`/api/agent/start`, `/api/agent/stop`, `/api/demo/scenario`) are gated by server-only `AEGIS_CONTROL_TOKEN` + `AEGIS_DASHBOARD_ADMIN_SECRET`.
- **Public View-Only Judge Mode:** By default, visitors have zero trade or control privileges (`View-Only Judge Mode`).
- **Source Mode Truthfulness:**
  - `MARKET_ONLY` displays real official OKX ATK CLI (`@okx_ai/okx-trade-cli@1.4.8`, `site=tr`) market observations, SHA-256 stdout/result digests, and `account_known=false` rendered explicitly as `UNAVAILABLE (not $0)`.
  - `MOCK` scenarios are tagged `MOCK SCENARIO` with `execution_status=NOT_SENT` and are never claimed as exchange executions.
  - `pnl` is reported as `null (NOT_TESTED)`.

## Routes
- `/` — **1-Screen Autonomous Control & Story:** Header bar, Scenario Switcher (`REAL ATK MARKET -> NO_TRADE` vs `SYNTHETIC UNSAFE STATE -> HALT`), 7-step pipeline (`Observe -> Classify -> Reason -> Risk Gate -> Action/No-Trade -> Verify -> Audit`) with measured durations, Explainable Verdict Card with deterministic rule IDs, SSE/SQLite Event Timeline, Capabilities matrix, and `Inspect Proof` modal.
- `/service` — **Use as Service (`GET /api/v1/service` & `POST /api/v1/risk/evaluate`):** Target customer positioning, interactive pre-trade evaluator (`1 BTC -> HALT: excess_order_notional` vs `0.0001 BTC -> REVIEW`), `order_permission=false`, `execution_authority=false`, canonical `assessment_sha256`, server-to-server cURL snippet, proposed pricing hypothesis (`PROPOSED_NOT_BILLED`), and `OKX.AI compatible service — listing readiness not confirmed (NOT_LISTED)`.
- `/avalanche` — **Avalanche Fuji (43113) Identity & Receipt Verifier:** Live Viem JSON-RPC connection to Fuji C-Chain (`43113`), ERC-8004 `ownerOf`/`tokenURI` read-back, `RiskDecisionRegistry.sol` SHA-256 receipt read-back, and explicit off-chain vs on-chain boundary.
- `/.well-known/erc8004-agent.json` — Static ERC-8004 registration metadata template (`publicOriginStatus: PUBLIC_NOT_VERIFIED`).

## Commands

```bash
cd frontend
npm test              # Vitest truthfulness & null-safety suite
npx tsc --noEmit      # TypeScript strict check
npm run build         # Production Next.js build
npm run dev           # Start on http://localhost:3000
```
