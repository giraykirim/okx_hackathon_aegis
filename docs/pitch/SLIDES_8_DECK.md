# AEGIS — 8-Slide 10-Minute Jury Presentation (`<= 9:30` Rehearsed Timing + Speaker Notes)

**Product:** AEGIS — Autonomous Pre-Trade Risk-Checking & Self-Monitoring Service for Agentic Trading  
**Authoritative Rubric:** `Agentic_Hackathon_Judge_Criteria.xlsx` (`Criteria!A1:F8`, 100 Points)  
**Target Rehearsed Duration:** **9 minutes 15 seconds** (strictly `<= 9:30` to leave buffer before Judge Q&A)

---

## P3-03 Exact 8-Slide Timing & Rubric Map

| Slide # | Exact P3-03 Slide Topic | Rubric Focus | Duration | Cumulative Time |
|---|---|---|---|---|
| **Slide 1** | **Unsafe Autonomous Trading Agent Problem & Memorable User Story** | A. Innovation & Real-World Value (15 pts) | `1:00` | `0:00 – 1:00` |
| **Slide 2** | **Who Buys This: Financial Agent Developers/Operators & Problem Economics** | A. Innovation & Real-World Value (10 pts) | `0:50` | `1:00 – 1:50` |
| **Slide 3** | **What AEGIS Sells: Reusable Pre-Trade Risk-Check Service (`/api/v1/risk/evaluate`)** | A. Value + F. OKX Integration (10 pts) | `1:10` | `1:50 – 3:00` |
| **Slide 4** | **Multi-Step Real ATK-Backed Autonomous Loop & LAYA / EVREN / Hard Policy Boundary** | B. Agentic Design (20 pts) | `1:15` | `3:00 – 4:15` |
| **Slide 5** | **2-Minute LIVE Verified Demo + Deliberate Refusal of Unsafe Trade** | C. Demo & Presentation (20 pts) | `2:00` | `4:15 – 6:15` |
| **Slide 6** | **Avalanche Fuji (43113): True ERC-8004 Identity + `RiskDecisionRegistry.sol` & Honest Verification** | E. Avalanche Integration (10 pts) | `1:10` | `6:15 – 7:25` |
| **Slide 7** | **What We Actually Measured: Technical Reliability & LAYA Base-vs-Tuned Held-Out Placeholders** | D. Technical Execution (15 pts) | `1:00` | `7:25 – 8:25` |
| **Slide 8** | **Go-To-Market, Hypothetical Business Model, OKX.AI Readiness, Limitations & Next Step** | A. GTM + F. OKX.AI + C. Q&A | `0:50` | `8:25 – 9:15` |

---

## Slide 1 — Unsafe Autonomous Trading Agent Problem & Memorable User Story (`0:00 – 1:00`)

### On-Slide Visuals
- **Headline:** *One Hallucinated Quantity or Blind Retry Wipes Out Weeks of Agent Strategy*
- **The 3:00 AM Operator Story:**
  - A developer launches an LLM-powered BTC rebalance agent with a `$25 USDT` per-order risk budget.
  - **Failure 1 (Hallucinated Sizing):** The LLM misreads decimal precision and proposes `BUY 1.0 BTC` (`$81,648.60 USDT` notional at live OKX TR price).
  - **Failure 2 (Timeout Retry / Unknown Prior Order):** An exchange API request times out; the agent assumes the order failed and submits it a second time (`unresolved_prior_order` + `duplicate_intent`).
  - **Failure 3 (Silent `$0` Balance Fallback):** When an account query fails (`account_known = false`), naive wrapper code defaults `balance = 0.0` instead of halting on an operational blind spot.
- **Root Cause:** Giving probabilistic models or untrusted caller JSON direct execution authority over exchange keys.

### Speaker Notes (`1:00`)
> *"Imagine you are an indie quant or a fintech team running an autonomous trading agent at 3 AM. Your prompt instructs the agent to trade at most $25 of BTC-USDT. First, the LLM misformats a decimal and proposes buying 1 full Bitcoin—$81,648 of notional exposure. Or an exchange call times out, and because the agent doesn't track unresolved prior order state, it retries the trade and doubles your position. Worse, when an account read fails, naive code displays $0 balance instead of halting. Autonomous trading fails today because probabilistic models are wired directly to execution tools without an independent, fail-closed risk gate."*

---

## Slide 2 — Who Buys This: Financial Agent Developers/Operators & Problem Economics (`1:00 – 1:50`)

### On-Slide Visuals
- **Target Customer (`GET /api/v1/service` → `target_customer`):**
  1. **Builders of Autonomous CEX/DeFi Trading Agents** (LangChain, MCP, Onchain OS, custom Python bots).
  2. **AI Trading Skill & Strategy Providers** publishing tools into agent ecosystems.
  3. **Desk & Treasury Automation Operators** managing multi-agent execution limits.
- **Concise Problem Economics:**
  - **Cost of a Single Uncaught Agent Fault:** `$500 – $80,000+` in unintended notional exposure, crossed-spread slippage, or duplicate fills.
  - **Cost of Building In-House:** Maintaining exchange instrument tick/lot sync, subprocess isolation, operational regime anomaly classification, and immutable audit trails for every bot.
  - **Cost of Calling AEGIS (Proposed Hypothesis):** **`$0.01 USD` per pre-trade check** (or **`$99/mo`** for `10,000` checks). Blocking **one** `$25` duplicate trade pays for **2,500** AEGIS assessments.

### Speaker Notes (`0:50`)
> *"Who buys AEGIS? Developers and operators of financial agents—teams building on MCP, OKX Onchain OS, or custom Python loops. Look at the unit economics: a single uncaught decimal error or duplicate retry costs hundreds or thousands of dollars in immediate slippage or unwanted exposure. Building an isolated, exchange-synced pre-trade risk engine from scratch takes weeks. At our proposed hypothesis price of one cent per pre-trade assessment, preventing a single $25 duplicate order pays for 2,500 risk checks."*

---

## Slide 3 — What AEGIS Sells: Reusable Pre-Trade Risk-Check Service (`1:50 – 3:00`)

### On-Slide Visuals
- **Service Contract ([`contracts/service-openapi.yaml`](../../contracts/service-openapi.yaml) & [`docs/product/service.md`](../product/service.md)):**
  - `GET /api/v1/service` — Public capability, SLA, pricing hypothesis, and OKX.AI readiness descriptor.
  - `POST /api/v1/risk/evaluate` — Protected by `X-AEGIS-Key`, `30 req/min` rate limit, `4,096-byte` body cap, and `8s` deadline.
- **Strict Input/Output Security Boundary (Proven in [`backend/evidence/amendment-http.json`](../../backend/evidence/amendment-http.json)):**
  - **Input (`RiskRequest`, `additionalProperties: false`):** Accepts only `{symbol: "BTC-USDT", action: "BUY"|"SELL", quantity, client_request_id}`.
  - **Spoofed Caller Input Rejected (`HTTP 422`):** Passing caller-supplied `balance`, `market_price`, or `order_permission` is rejected at schema validation.
  - **Server-Side ATK Provenance:** AEGIS independently executes `@okx_ai/okx-trade-cli@1.4.8` on `site=tr` and returns `assessment` (`REVIEW` | `HALT`), `order_permission: false`, `execution_authority: false`, and canonical `assessment_sha256`.

### Speaker Notes (`1:10`)
> *"What AEGIS sells is a reusable, stateless pre-trade risk-check API: `POST /api/v1/risk/evaluate`. An external trading agent sends only its proposed symbol, side, and quantity. If a caller tries to spoof their account balance or pass `order_permission: true` in the request body, our schema rejects it with HTTP 422—proven in `amendment-http.json`. Instead of trusting the caller, AEGIS spawns the official OKX Agent Trade Kit CLI server-side, checks spread, freshness, lot size, and notional caps, and returns a SHA-256 signed `REVIEW` or `HALT` receipt with `order_permission: false` and `execution_authority: false`."*

---

## Slide 4 — Multi-Step Real ATK-Backed Autonomous Loop & LAYA / EVREN / Hard Policy Boundary (`3:00 – 4:15`)

### On-Slide Visuals
- **7-Step Autonomous Loop ([`backend/evidence/http-smoke.json`](../../backend/evidence/http-smoke.json) & [`backend/evidence/jury-manifest.json`](../../backend/evidence/jury-manifest.json)):**
  1. **`OBSERVE` (`1,282 – 1,324 ms`):** Real `@okx_ai/okx-trade-cli@1.4.8` subprocess reads (`market ticker BTC-USDT --site tr --demo --json` in `721.3ms` + `market instruments` in `561.1ms`).
  2. **`CLASSIFY (LAYA)`:** Operational risk classifier outputs `CONTINUE`, `REVIEW`, or `HALT` — **never** a BTC price prediction, and `CONTINUE` never grants order permission.
  3. **`REASON (EVREN)`:** Bounded JSON `DecisionProposal` (`BUY`, `SELL`, `NO_TRADE`); tools disabled (`tools=[]`); abstains cleanly (`NO_TRADE`) when unavailable.
  4. **`RISK GATE (Deterministic Python Policy)`:** Final execution authority enforcing 14 fail-closed rules (`live_mode_disabled`, `account_state_unavailable`, `unresolved_prior_order`, `duplicate_intent`, `excess_order_notional`, `stale_feed`).
  5. **`ACTION / NO_TRADE`** → 6. **`VERIFY`** → 7. **`AUDIT`** (atomic SQLite journal + SHA-256 receipt).

### Speaker Notes (`1:15`)
> *"Inside AEGIS, our autonomous loop runs seven strict steps without human prompting. Step 1 invokes the real `@okx_ai/okx-trade-cli@1.4.8` Node binary in an isolated subprocess and hashes both stdout and parsed JSON. Step 2 runs LAYA to classify operational health as `CONTINUE`, `REVIEW`, or `HALT`. Step 3 runs EVREN with tool-calling disabled so it can only emit a schema-validated JSON proposal. Step 4 is our hard boundary: deterministic Python policy is the sole execution authority. If the feed is stale, account state is unknown, a prior order is unresolved, or notional exceeds $25, Python halts the trade regardless of what any model says."*

---

## Slide 5 — 2-Minute LIVE Verified Demo + Deliberate Refusal of Unsafe Trade (`4:15 – 6:15`)

### On-Slide Visuals & Live Demo Script (`2:00` Choreography)
- **Part 1 (`0:00 – 0:45`) — `/` Main Dashboard (Scenario 1 vs Scenario 2):**
  - **Scenario 1 (`REAL ATK MARKET -> NO_TRADE`):** Live `MARKET_ONLY` observation from OKX TR (`BTC-USDT = $81,648.60`, spread `0.024 bps`), `account_known=false` rendered as **`UNAVAILABLE (not $0)`**, and **`Inspect Proof`** modal showing exact ATK CLI command and `stdout_sha256` (`011119fc...`).
  - **Scenario 2 (`SYNTHETIC UNSAFE STATE -> HALT [MOCK SCENARIO]`):** Click **Unknown Prior Order** (`unresolved_prior_order`) and **Duplicate Intent** (`duplicate_intent`). Even when LAYA outputs `CONTINUE (100%)` and a model proposes `BUY 0.0001 BTC`, the deterministic gate refuses execution (`verdict=HALT`, `execution_status=NOT_SENT`).
- **Part 2 (`0:45 – 1:25`) — `/service` B2B Pre-Trade Evaluation:**
  - Compare **Preset A (`1 BTC -> HALT: excess_order_notional`, `$81,648.60 > $25 cap`, SHA-256 `0x166c9307...`)** vs **Preset B (`0.0001 BTC -> REVIEW`)**.
- **Part 3 (`1:25 – 2:00`) — `/avalanche` Live Fuji 43113 RPC Verifier:**
  - Show live Fuji connection (`chainId=43113`), verified official ERC-8004 registries, and `RiskDecisionRegistry.sol` receipt verification.

### Speaker Notes (`2:00`)
> *(Execute the 2-minute live walkthrough across `/`, `/service`, and `/avalanche`. Highlight the deliberate refusal of the unsafe 1 BTC order on `/service` and the `unresolved_prior_order` / `duplicate_intent` vetoes on `/`, plus the `View-Only Judge Mode` badge showing public visitors have zero mutation privileges.)*

---

## Slide 6 — Avalanche Fuji (43113): True ERC-8004 Identity + `RiskDecisionRegistry.sol` & Honest Verification (`6:15 – 7:25`)

### On-Slide Visuals
- **On-Chain vs. Off-Chain Boundary ([`web3/PROOF.md`](../../web3/PROOF.md) & [`web3/fuji-proof-manifest.json`](../../web3/fuji-proof-manifest.json)):**
  - **Off-Chain:** Python policy engine, OKX ATK CLI, LAYA classifier, EVREN LLM.
  - **On-Chain (Fuji C-Chain `43113` only; no custom L1 or ICM claimed):**
    1. **Official ERC-8004 `IdentityRegistry`:** [`0x8004A818BFB912233c491871b3d84c89A494BD9e`](https://testnet.snowtrace.io/address/0x8004A818BFB912233c491871b3d84c89A494BD9e) — **Registered & Verified on-chain (`agentId = "273"`, `tx: 0x7b61d86a11c815b301d44d6062c938bd7c8995c9d81332f9bb476c0bc436f08b`, block `#59600465`)** in [`web3/registration-proof.json`](../../web3/registration-proof.json).
    2. **Official ERC-8004 `ReputationRegistry`:** [`0x8004B663056A597Dffe9eCcC1965A193B7388713`](https://testnet.snowtrace.io/address/0x8004B663056A597Dffe9eCcC1965A193B7388713) — verified live via `eth_getCode` (`130 bytes` proxy); zero self-awarded feedback (`"No independent feedback yet"`).
    3. **Custom `RiskDecisionRegistry.sol` ([`web3/contracts/RiskDecisionRegistry.sol`](../../web3/contracts/RiskDecisionRegistry.sol)):** Compiled (`solc 0.8.37`), tested in local EVM (`3/3 PASS`), **deployed on Fuji at [`0x5ae5642cd6a02e0834b3fba822d442429aeadc5f`](https://testnet.snowtrace.io/address/0x5ae5642cd6a02e0834b3fba822d442429aeadc5f)** (`deploy tx: 0x7cb24d8f...`), and verified on-chain anchoring the real backend `HALT` receipt (`record tx: 0xcb226fb049a7052ca8889d585dfcb3a1cf66528e318a60c7ff2c9b43a67de2f1`, block `#59599653`, `decisionHash: 0x0fa71a80...`).
- **Honest Verification Status:** On-chain identity (`#273`), contract deployment, and `HALT` receipt readback are **`PASS` (`VERIFIED_ON_CHAIN`)**; submission-to-confirmation latency is **`NOT_MEASURED` (`measured_confirmation_ms: null`)** because verification ran post-confirmation.

### Speaker Notes (`1:10`)
> *"On Slide 6, we show our Avalanche Fuji C-Chain integration and our strict anti-fabrication rules. First, AI inference and OKX ATK run off-chain. On Fuji (`chainId = 43113`), we minted and verified ERC-8004 `agentId = 273` (`0x7b61d8...`) on the official `IdentityRegistry` (`0x8004A818...4BD9e`) and verified zero self-ratings on the `ReputationRegistry`. Second, we deployed `RiskDecisionRegistry.sol` on Fuji (`0x5ae5642c...`) and anchored our real backend HALT decision digest (`0x0fa71a80...`, tx `0xcb226fb0...`), verifying the stored digest and caller via independent RPC read-back. Because verification ran post-confirmation, confirmation latency is honestly reported as `null` (`NOT_MEASURED`) rather than invented."*

---

## Slide 7 — What We Actually Measured: Technical Reliability, LAN Model Proof & Quarantine Boundary (`7:25 – 8:25`)

### On-Slide Visuals
- **1. Verified Technical Reliability & Latencies ([`docs/JURY_EVIDENCE.md`](../JURY_EVIDENCE.md), [`backend/evidence/system-status-http.json`](../../backend/evidence/system-status-http.json)):**
  - **Automated Test Suites:** `208 / 208 PASS` (`backend` isolated pytest) + `57 / 57 PASS` (`frontend` Vitest truthfulness & UI) + `3 / 3 PASS` (`web3` EVM Solidity tests) + `253 / 253 PASS` (`ml` offline verification) = **`521 / 521 PASS` (`0` failures)**.
  - **Measured Official ATK Subprocess & End-to-End Latencies (`site=tr`):**
    - Pre-trade service checks: `ticker` = **`536–721 ms`**, `instruments` = **`543–561 ms`** (total 2-command ATK read = **`1,079.80–1,282.47 ms`**).
    - Full 7-step HTTP cycle (`18d805b9...` with real ATK + LAN LAYA + EVREN): **`12.745 s`** wall time (`policy check = 0.300 ms`; sample count = `1`, not claimed as p50/p95 SLA).
  - **SQLite Atomic Rollback & Idempotency:** Verified via abort-trigger regression (`test_store.py` / `test_agent.py`); zero duplicate order placement on crash/restart.
- **2. LAYA LAN Service, Versioned Policy v2 & Quarantined CUDA Findings ([`backend/evidence/laya-lan-contract.json`](../../backend/evidence/laya-lan-contract.json), [`ml/PERSON1_POLICY_V2_NOTE.md`](../../ml/PERSON1_POLICY_V2_NOTE.md)):**
  - **EVREN Discovery & Proposal:** `PASS` (`deepseek-v4.1-flash` discovered & verified in `system-status-http.json`; bounded JSON proposal, `tools=[]`).
  - **LAYA Live LAN Contract & Abstention:** `PASS` (`aegis-laya-base-f38a07fa01db`, `shadow_only=true`); abstains (`REVIEW`, `abstained=true`) on legacy observations missing operational context and remains advisory.
  - **Policy v2 & Quarantined V2 CUDA Run:** `ml/label_policy_v2.py` achieves **`161 / 161` (100%) agreement** with frozen human-reviewed candidates; crossing all `39` valid profiles across `4` quantities (`156` rows) in V2 head-only CUDA training (`v2-20261017T141303599045Z`) proved **`39 / 39` (100%) quantity invariance** (`0` changed predictions) and converged to majority `REVIEW` (`76/161`), confirming why `base` + deterministic Python vetoes remain the active safety boundary.

### Speaker Notes (`1:00`)
> *"Slide 7 shows only what we actually measured—zero invented accuracy claims or fake SLAs. Across our codebase, 521 automated tests pass across backend, frontend, EVM contracts, and ML suites. We measured real official OKX ATK subprocess latencies on `site=tr` (`1.08–1.28 s` per two-command check) and a complete 7-step cycle with live ATK, LAN LAYA, and EVREN (`12.75 s` for one sample, with `0.300 ms` policy evaluation). On the ML side, our versioned `v2` label policy matches `161/161` human-confirmed review labels, and our 4-quantity grid eliminated quantity shortcuts (`39/39` profile invariance), proving why LAYA stays in `base` shadow/advisory mode while deterministic Python policy retains final veto authority."*

---

## Slide 8 — Go-To-Market, Hypothetical Business Model, OKX.AI Readiness, Limitations & Next Step (`8:25 – 9:15`)

### On-Slide Visuals
- **Hypothetical Business Model (`status: PROPOSED_NOT_BILLED`, `payment_integration: NOT_IMPLEMENTED`):**
  - **Pay-Per-Assessment Tier:** **`$0.01 USD` / assessment** (target for A2MCP per-call settlement in USDT/USDG).
  - **B2B Operator Tier:** **`$99 USD / month`** (`10,000` assessments included + dedicated policy ruleset + Fuji receipt anchoring).
- **OKX.AI Service Listing Readiness ([`docs/product/OKX_AI_LISTING_READINESS.md`](../product/OKX_AI_LISTING_READINESS.md), [`backend/evidence/okxai-onboarding.json`](../../backend/evidence/okxai-onboarding.json)):**
  - Research & Official CLI Pre-Check: **`VERIFIED`** (`onchainos 4.6.4` installed, owner login & ASP eligibility check passed; no registration/payment submitted).
  - Integration Feasibility: **`POSSIBLE / NOT_LISTED`** (`GET /api/v1/service` + `POST /api/v1/risk/evaluate` + `contracts/service-openapi.yaml` ready; temporary protected HTTPS tunnel verified in [`backend/evidence/public-service-http.json`](../../backend/evidence/public-service-http.json)).
  - Remaining Steps: Durable HTTPS hosting, marketplace auth compatibility, x402/SDK settlement (`MISSING`), and platform review (`NOT_LISTED`).
- **Current Limitations & Immediate Next Step:**
  - **Limitations:** Dashboard remains local (temporary HTTPS covers restricted risk service only), OKX demo order submission/reconciliation `NOT_TESTED` (authenticated demo account read `PASS` in `backend/evidence/exchange-readiness.json`, zero orders sent), Fuji tx confirmation latency `NOT_MEASURED`, seconds-scale latency (`~1.1–1.4s` service check, non-HFT), `pnl = null`.
  - **Next Step:** Promote temporary HTTPS risk endpoint to durable multi-tenant hosting, wire full 16-field trusted operational context (`laya_context.py`) into shadow evaluation, and submit the A2MCP provider package for OKX.AI review.

### Speaker Notes (`0:50`)
> *"Finally, Slide 8 summarizes our go-to-market path, OKX.AI readiness, and honest limitations. Our pricing—$0.01 per check or $99/month—is clearly labeled a commercial hypothesis (`PROPOSED_NOT_BILLED`). Using official `onchainos 4.6.4`, we verified ASP onboarding eligibility and proved our protected risk API over a temporary HTTPS tunnel, while clearly reporting that marketplace listing is `NOT_LISTED`, x402 billing is not implemented, and demo order submission remains `NOT_TESTED`. Our next steps are durable HTTPS hosting, full shadow context telemetry, and submitting our A2MCP package.*  
> ***AEGIS knows when to act, when to investigate, and when to stop — with an on-chain identity anyone can verify.*** *Thank you—we welcome your toughest questions."*

---

## 2. Kısa Türkçe Prova (Rehearsal) & Sahne Akışı Rehberi (PROMPT 16)

1. **Slayt 1–2 (`0:00 – 1:50`) — Problem ve Kim Satın Alır:**
   - *"Otonom AI trading botları bugün LLM çıktılarını doğrudan borsa emir araçlarına bağladıkları için çöküyor: yanlış bir ondalıkla 25 dolar yerine 1 BTC (81.648 dolar) emir göndermek, zaman aşımına uğrayan emri tekrar gönderip pozisyonu ikiye katlamak (`unresolved_prior_order` / `duplicate_intent`) veya bakiye okunamadığında bunu 0 dolar sanmak. AEGIS, finansal ajan geliştiren ekipler için bağımsız ve fail-closed bir işlem öncesi (pre-trade) risk servisi sunar."*
2. **Slayt 3–4 (`1:50 – 4:15`) — Ne Satıyoruz & 7 Adımlı ATK Döngüsü:**
   - *"Dış ajanlar emir göndermeden önce `POST /api/v1/risk/evaluate` servisimizi çağırır. Arayanın gönderdiği sahte bakiye veya izin bayrakları `HTTP 422` ile reddedilir. AEGIS, sunucu tarafında resmi `@okx_ai/okx-trade-cli@1.4.8` aracını (`site=tr`) çalıştırır. LAYA operasyonel durumu (`CONTINUE/REVIEW/HALT`) sınıflandırır, EVREN şema doğrulamalı öneri üretir; ancak nihai yetki her zaman deterministik Python politikasındadır (`order_permission=false`)."*
3. **Slayt 5 (`4:15 – 6:15`) — 2 Dakikalık Canlı Demo (Scene A, B, C, D):**
   - **Scene A (`/`):** Gerçek OKX TR ATK gözlemi (`~1,324 ms`), `UNAVAILABLE (not $0)` bakiye doğruluğu ve `NO_TRADE` kararı; `Inspect Proof` ile CLI `stdout_sha256` kanıtı.
   - **Scene B (`/`):** Kontrollü `MOCK SCENARIO` ile `unresolved_prior_order` ve `duplicate_intent` tetiklenmesi; LAYA `%100 CONTINUE` dese bile deterministik kapının emri reddetmesi (`execution_status=NOT_SENT`).
   - **Scene C (`/service` & `/avalanche`):** `/service` üzerinde `1 BTC -> HALT (excess_order_notional)` reddi; `/avalanche` üzerinde Fuji `43113` RPC bağlantısı, resmi ERC-8004 `IdentityRegistry` üzerinde mint edilen **`Agent #273`** (`tx: 0x7b61d8...`) ve `RiskDecisionRegistry.sol` (`0x5ae5642c...`) üzerinde zincire yazılan gerçek `HALT` karar fişinin (`tx: 0xcb226fb0...`) canlı doğrulaması.
   - **Scene D:** Kimlik doğrulamalı OKX demo hesap okuması (`account_known=true`) kanıtlanmış olup, emir gönderimi güvenlik gereği kapalıdır (`NOT_SENT` / `live_execution_enabled=false`).
4. **Slayt 6–8 (`6:15 – 9:15`) — Avalanche Fuji, Ölçülen Metrikler & Kapanış:**
   - *"AI çıkarımı ve OKX ATK off-chain çalışır; Avalanche Fuji (`43113`) üzerinde resmi ERC-8004 `Agent #273` kimliğimiz ve `RiskDecisionRegistry.sol` üzerindeki SHA-256 HALT karar fişimiz (`0x0fa71a80...`) zincir üstünde doğrulanmıştır. Toplam 521 otomatik testimiz (`208` backend, `57` frontend, `3` EVM, `253` ML) geçmektedir. V2 politika revizyonumuz `161/161` insan onaylı veriyle tam uyumludur; LAYA shadow/advisory modda kalırken nihai emir vetosu deterministik Python politikasındadır."*
   - **Kapanış Cümlesi:** *"AEGIS knows when to act, when to investigate, and when to stop — with an on-chain identity anyone can verify."*

