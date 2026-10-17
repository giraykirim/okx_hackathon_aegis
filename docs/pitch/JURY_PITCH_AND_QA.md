# AEGIS — Jury Pitch, 12+ Hostile Judge Q&As & Public/Backup Demo Runbook

**Owner:** Person 3 (`docs/pitch/**`)  
**Authoritative Rubric Source:** `Agentic_Hackathon_Judge_Criteria.xlsx` (`Criteria!A1:F8`, 100 Points)  
**Companion Deck:** See [`docs/pitch/SLIDES_8_DECK.md`](./SLIDES_8_DECK.md) for the complete 8-slide `9:15` presentation and speaker notes.

---

## 1. Rubric Mapping Summary (100 Points)

| Category | Weight | AEGIS Proof Surface |
|---|---|---|
| **A. Innovation & Real-World Value** | **25 pts** | Originality (10), Clear problem & target user (5), Market potential / business model hypothesis (5), Ready-to-go-market architecture (5) → Demonstrated on `/service` (`GET /api/v1/service`, `POST /api/v1/risk/evaluate`) |
| **B. Agentic Design** | **20 pts** | End-to-end autonomy without step-by-step prompting (10), Multi-step reasoning & tool selection with strict safety boundaries (10) → Demonstrated on `/` 7-step pipeline |
| **C. Demo & Presentation** | **20 pts** | Working live demo (5), UX design (5), Pitch quality & Q&A (10) → `/` (1-Screen Story), `/service`, `/avalanche`, and `Inspect Proof` drawer |
| **D. Technical Execution** | **15 pts** | Working product (5), Architecture quality (5), Technical difficulty (5) → 97 backend tests + 7 frontend truthfulness tests + 3 EVM tests + frozen OpenAPI v2 + additive service schema |
| **E. Avalanche Integration** | **10 pts** | C-Chain / Fuji 43113 integration (5), Avalanche strengths lifecycle (5) → `/avalanche` Viem RPC read-back + `web3/contracts/RiskDecisionRegistry.sol` + `web3/PROOF.md` |
| **F. OKX Integration** | **10 pts** | Official OKX Agent Trade Kit `@okx_ai/okx-trade-cli@1.4.8` subprocess reads (5), OKX.AI service compatibility & honest `NOT_LISTED` readiness matrix (5) |

---

## 2. Hostile Judge Q&A — 14 Realistic Questions & Direct, Non-Evasive Answers

### Q1: "Does your AI model (LAYA or EVREN) or Python risk engine execute on the Avalanche blockchain?"
- **Direct Answer:** **No.** Agent reasoning (EVREN), operational classification (LAYA), deterministic Python policy, and OKX Agent Trade Kit subprocesses all execute **off-chain**. Avalanche Fuji C-Chain (`chainId = 43113`) is used strictly for **ERC-8004 agent identity registration** (`0x8004A818BFB912233c491871b3d84c89A494BD9e`) and **anchoring 32-byte SHA-256 decision receipts** (`RiskDecisionRegistry.sol`) so external callers can verify that an off-chain risk assessment was not altered after the fact.

### Q2: "Why did your demo not place a live or demo order on OKX today?"
- **Direct Answer:** First, **live order execution is permanently disabled** in server code (`live_execution_enabled = false`) by design. Second, for OKX Demo trading in our region (`site=tr`, `tr.okx.com`), authenticated demo endpoints (`account balance`, `spot orders`) returned OKX regional restriction error `50110` during verification (`backend/evidence/latest.json`). Rather than faking an order fill, AEGIS automatically operates in truthful **`MARKET_ONLY`** mode using real `@okx_ai/okx-trade-cli@1.4.8` market data (`ticker` and `instruments`) and fails closed to `NO_TRADE` because `account_state_unavailable` is active.

### Q3: "Is AEGIS actually listed on the OKX.AI Marketplace right now?"
- **Direct Answer:** **No (`listing_status: NOT_LISTED`, `integration_feasibility: POSSIBLE`).** We researched the official OKX.AI architecture (`okx.com/learn/okx-ai` + ASP documentation), which runs on Onchain OS (`okx/onchainos-skills`) and requires an OKX Agentic Wallet, shared onchain Agent Identity, A2MCP (pay-per-call) or A2A (escrow) settlement in USDT/USDG, and marketplace review. We built the compatible HTTP/JSON evaluation service (`GET /api/v1/service`, `POST /api/v1/risk/evaluate`) and explicitly display our 5-part Readiness Matrix (`PASS` / `VERIFYING` / `MISSING` / `NOT_LISTED`) on `/service`.

### Q4: "If deterministic Python rules have the final veto, why do you need LAYA or EVREN at all?"
- **Direct Answer:** Deterministic rules catch known structural violations (like `quantity > max_notional`, `duplicate_intent`, or `stale_feed`), but they cannot classify multi-feature operational degradation patterns before a hard threshold breaks, nor can they synthesize a trade proposal from market context. **LAYA** (`CONTINUE` / `REVIEW` / `HALT`) is designed to classify operational regime so degraded conditions can tighten or halt the gate early; **EVREN** generates a bounded, schema-validated action proposal (`DecisionProposal` with `tools=[]`); and **deterministic Python** guarantees that neither model can ever bypass hard safety limits.

### Q5: "Does LAYA predict whether Bitcoin's price will go up or down?"
- **Direct Answer:** **No.** LAYA is an **operational risk classifier** (`CONTINUE`, `REVIEW`, `HALT`), not a BTC price-prediction oracle or alpha signal generator. Furthermore, even when LAYA outputs `CONTINUE` with `100%` confidence, `order_permission` remains `false` until every deterministic risk rule passes.

### Q6: "Did you actually deploy `RiskDecisionRegistry.sol` and mint an ERC-8004 `agentId` on Fuji, or is it local?"
- **Direct Answer:** Here is the exact split in [`web3/fuji-proof-manifest.json`](../../web3/fuji-proof-manifest.json):
  1. **Live on Fuji (`PASS`):** We verified against live Fuji RPC (`https://api.avax-test.network/ext/bc/C/rpc`, block `#59593917`) that both official ERC-8004 contracts (`IdentityRegistry: 0x8004A818BFB912233c491871b3d84c89A494BD9e` and `ReputationRegistry: 0x8004B663056A597Dffe9eCcC1965A193B7388713`) have deployed bytecode and respond to `name() = "AgentIdentity"`, `symbol() = "AGENT"`, and `ownerOf(1)`.
  2. **Compiled & Verified in Local EVM (`3/3 PASS`):** `RiskDecisionRegistry.sol` is compiled (`solc 0.8.37`, `2,135 bytes`) and passes 3/3 EVM unit + integration tests ([`web3/tests/risk-decision-registry.test.ts`](../../web3/tests/risk-decision-registry.test.ts)) using the real canonical SHA-256 digest (`0x166c9307...`) from [`backend/evidence/amendment-http.json`](../../backend/evidence/amendment-http.json).
  3. **Live Broadcast on Fuji (`NOT_TESTED`, `verified=false`):** Because we do not have a funded disposable Fuji wallet (`FUJI_PRIVATE_KEY`) or public HTTPS host configured in this local environment, we report `agent_id: null` and `contract_address: null` rather than fabricating a transaction hash. Running `npm run prove:fuji` with a funded test key executes both transactions and writes the live receipts automatically.

### Q7: "Why does `POST /api/v1/risk/evaluate` take ~1.1 to 1.4 seconds? Isn't that too slow for trading?"
- **Direct Answer:** It is intentionally **seconds-scale**, not sub-millisecond HFT. On every evaluation request, AEGIS spawns two isolated `@okx_ai/okx-trade-cli@1.4.8` subprocesses (`market ticker` in `~536–721ms` and `market instruments` in `~543–561ms` on `site=tr`, recorded in [`backend/evidence/jury-manifest.json`](../../backend/evidence/jury-manifest.json)) to verify live market price, spread, tick size, and lot size server-side instead of trusting the caller. That ~1.2s overhead is negligible for autonomous agentic workflows (DCA, portfolio rebalancing, swing strategies, DeFi treasury agents) where preventing a catastrophic hallucinated order is far more important than millisecond latency.

### Q8: "What stops an external caller from passing fake balances or `market_fresh: true` into `/api/v1/risk/evaluate`?"
- **Direct Answer:** `RiskRequest` is strictly locked with Pydantic `extra='forbid'` (`additionalProperties: false` in [`contracts/service-openapi.yaml`](../../contracts/service-openapi.yaml)), accepting **only** `{symbol, action, quantity, client_request_id}`. Any request containing caller-supplied `balance`, `market_price`, `order_permission`, or trust flags is immediately rejected with **`HTTP 422 Unprocessable Entity`** (proven in [`backend/evidence/amendment-http.json`](../../backend/evidence/amendment-http.json)).

### Q9: "Why does the dashboard show `UNAVAILABLE (not $0)` for account balance instead of `$0.00`?"
- **Direct Answer:** In financial systems, treating an unauthenticated or failed balance query (`account_known = false`) as `$0.00` is a dangerous bug that masks connectivity failures or misleads position-sizing logic. Our UI and backend strictly distinguish a verified zero balance (`$0.00 USDT`) from an unknown account state (`UNAVAILABLE (not $0)`), and the risk gate automatically halts trading with `account_state_unavailable`.

### Q10: "Can a judge or malicious user click 'Start Agent' or trigger trades if you share the dashboard URL?"
- **Direct Answer:** **No.** The Next.js frontend never exposes any backend tokens in `NEXT_PUBLIC_*` variables. By default, every visitor runs in **`View-Only Judge Mode`**. Mutating proxy routes (`/api/agent/start`, `/api/agent/stop`, `/api/demo/scenario`) require both a server-side `AEGIS_CONTROL_TOKEN` and a matching `X-AEGIS-Admin-Secret` header (`HTTP 403` otherwise). And even for an authenticated admin, `live_execution_enabled` is hardcoded `false`.

### Q11: "Why does `/api/v1/risk/evaluate` only return `REVIEW` or `HALT` in your recorded evidence, never `CLEAR_TO_PROCEED`?"
- **Direct Answer:** Because `CLEAR_TO_PROCEED` requires verified account state (`account_provenance = VERIFIED`) and healthy LAYA/EVREN checks. In `MARKET_ONLY` mode, external callers are evaluated without delegated exchange account credentials (`account_provenance = UNAVAILABLE`) and without LAN model inference during isolated service calls (`laya_status = SKIPPED`). Therefore, even when market freshness, spread, lot size, and $25 notional caps all **PASS** (as in our `0.0001 BTC` sample), AEGIS honestly returns **`REVIEW`** rather than over-claiming `CLEAR_TO_PROCEED`.

### Q12: "What happens when the LAN GPU server running LAYA or the EVREN API is unavailable or unconfigured?"
- **Direct Answer:** AEGIS fails closed and uses explicit advisory fallbacks (`backend/evidence/http-smoke.json` & `backend/evidence/MATRIX.md`). When LAYA or EVREN is unreachable or unconfigured, LAYA falls back to `REVIEW` (`reason: laya_url_not_configured` / `laya_unavailable`), EVREN abstains with `NO_TRADE` (`reason: evren_api_key_missing` / `evren_unavailable`), and the deterministic risk gate blocks any order execution.

### Q13: "What are your held-out accuracy and CUDA speedup numbers for LAYA base-vs-tuned?"
- **Direct Answer:** In [`backend/evidence/MATRIX.md`](../../backend/evidence/MATRIX.md) (Line 24) and [`backend/evidence/jury-manifest.json`](../../backend/evidence/jury-manifest.json), **LAYA LAN classification and CUDA VRAM / fine-tuning benchmarks are recorded as `NOT_TESTED` in this repository** (owned by Person 2 on the separate RTX machine). Per our strict honesty rule, we display an explicit placeholder (`[PLACEHOLDER: AWAITING_PERSON_2_HELD_OUT_EVAL_ARTIFACT]`) on Slide 7 and never invent model accuracy percentages or speedup multipliers.

### Q14: "Does anchoring receipts on Avalanche Fuji leak sensitive trading strategy or customer account data?"
- **Direct Answer:** **No.** `RiskDecisionRegistry.sol` only accepts `bytes32` cryptographic hashes (`decisionHash`, `runIdHash`, `policyVersionHash`) and an integer `verdictCode` (`0`, `1`, or `2`). No API keys, account balances, order quantities, or customer identifiers are ever written to calldata or contract storage.

### Q15: "Are you using an Avalanche Custom L1 or Interchain Messaging (ICM/Teleporter)?"
- **Direct Answer:** **No.** We use **Avalanche Fuji C-Chain (`chainId = 43113`) only**, where the official ERC-8004 `IdentityRegistry` and `ReputationRegistry` are deployed. We explicitly set `custom_l1_used: false` and `interchain_messaging_used: false` in [`web3/fuji-proof-manifest.json`](../../web3/fuji-proof-manifest.json) so we never over-claim unused protocol features.

---

## 3. Public Deployment Honesty & Backup Demo Recording Runbook (P3-03)

### Current Public Deployment Status: `LOCAL_ONLY` (`public_url: null`)
Per P3-03 security and truthfulness rules:
- We **never** call `http://127.0.0.1:3000` or `http://127.0.0.1:8000` a "public deployment", and we never claim `"deployed product"` unless a live HTTPS URL responds and its key UX workflow works end-to-end.
- Both `/api/v1/service` (`deployment_status: "LOCAL_ONLY"`, `public_url: null`) and `/.well-known/erc8004-agent.json` (`publicOriginStatus: "PUBLIC_NOT_VERIFIED"`, `endpoints: []`) state this honestly.
- **When deploying to a public HTTPS URL:**
  1. Deploy the Next.js frontend in **View-Only Judge Mode** by omitting `AEGIS_CONTROL_TOKEN` and `AEGIS_DASHBOARD_ADMIN_SECRET` in the public environment (private order/control endpoints are never exposed publicly without auth).
  2. Keep `POST /api/v1/risk/evaluate` protected behind `X-AEGIS-Key`, `30 req/min` rate limiting, and `4096-byte` payload limit.
  3. Set `AEGIS_PUBLIC_ORIGIN=https://<verified-domain>` only after `curl -fsSL https://<verified-domain>/.well-known/erc8004-agent.json` succeeds from an external check.

### Local Live Demo + Zero-Downtime Backup Runbook
1. **Start Backend (Person 1 FastAPI on `:8000`):**
   ```bash
   cd /Users/abdullah/okx_hackathon_aegis/backend
   AEGIS_SOURCE_MODE=MARKET_ONLY \
   AEGIS_OKX_SITE=tr \
   AEGIS_CONTROL_TOKEN=local-admin-control \
   AEGIS_SERVICE_API_KEY=local-service-key \
   uv run uvicorn aegis.app:app --host 127.0.0.1 --port 8000
   ```
2. **Start Frontend (Person 3 Next.js on `:3000`):**
   ```bash
   cd /Users/abdullah/okx_hackathon_aegis/frontend
   AEGIS_BACKEND_URL=http://127.0.0.1:8000 \
   AEGIS_CONTROL_TOKEN=local-admin-control \
   AEGIS_SERVICE_API_KEY=local-service-key \
   AEGIS_DASHBOARD_ADMIN_SECRET=demo-admin \
   npm run start
   ```
3. **Automatic Venue Wi-Fi / Offline Fallback & Backup Recording:**
   - Even if venue Wi-Fi or the backend server drops mid-pitch, `/` ([`page.tsx`](../../frontend/src/app/page.tsx)), `/service` ([`service/page.tsx`](../../frontend/src/app/service/page.tsx)), and `/avalanche` ([`avalanche/page.tsx`](../../frontend/src/app/avalanche/page.tsx)) automatically fall back to our real recorded HTTP evidence fixtures (`RECORDED HTTP PROOF` badge backed by [`backend/evidence/http-smoke.json`](../../backend/evidence/http-smoke.json) and [`backend/evidence/amendment-http.json`](../../backend/evidence/amendment-http.json)) with zero broken screens.
   - To capture a 2-minute backup screen recording before walking on stage, follow the exact `2:00` choreography in Slide 5 of [`docs/pitch/SLIDES_8_DECK.md`](./SLIDES_8_DECK.md) (`0:00–0:45` `/` Scenario 1 & Scenario 2 + `Inspect Proof`, `0:45–1:25` `/service` Preset A `1 BTC -> HALT` vs Preset B `0.0001 BTC -> REVIEW`, `1:25–2:00` `/avalanche` Fuji 43113 RPC verifier).
