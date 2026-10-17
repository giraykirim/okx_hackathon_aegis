# AEGIS — official 100-point rubric evidence map

Freeze core commit: eb2eea0a8cafaa1690f34f6ebdd77fbdc75d029c. This maps maximum rubric weights to measured evidence; it does not award points. The source is the user-provided authorized Prompt 00A transcription of the official workbook, replacing earlier weights. No independent workbook inspection or jury scoring is claimed.

| Criterion | Max | Measured state | Evidence / replay | Limit |
|---|---:|---|---|---|
| A1 Originality | 10 | Prototype demonstrated; originality judgment pending | [Architecture and operations](product/SERVICE_OPERATIONS.md), Python final gate, durable ambiguous-order journal and independently verified receipts | No uniqueness/patent/market-superiority study |
| A2 Problem and target user | 5 | DOCUMENTED | [One-pager](product/ONE_PAGER.md): trading-agent engineering teams; repeated/unsafe/unaudited submissions | Customer interviews not completed |
| A3 Market/business model | 5 | HYPOTHESIS | USD 0.01/evaluation or USD 99/team/month; [pilot](product/SERVICE_OPERATIONS.md) | No customers, billing, revenue or willingness-to-pay proof |
| A4 Ready to market | 5 | PARTIAL | Authenticated API, frozen contract, integration curl, seven-day pilot and [readiness checklist](product/OKX_AI_LISTING_READINESS.md) | Durable hosting, marketplace auth handoff, tenancy and acquisition remain missing |
| B1 Autonomous end-to-end work | 10 | PASS, local MARKET_ONLY | [Real HTTP run](../backend/evidence/system-status-http.json); one authenticated Start produces OBSERVE → CLASSIFY → REASON → RISK_CHECK → NO_TRADE → VERIFY → AUDIT | No per-step prompts; demonstration is read-only, agent stopped after proof |
| B2 Reasoning and tool/API process | 10 | PASS with explicit scope | Actual official MCP/CLI observations, LAN LAYA response, account-discovered EVREN proposal, deterministic gate and audit | Tool routing is a strict allowlist; LLM cannot choose arbitrary executable tools; LAYA abstains on incomplete context |
| C1 Working live demo | 5 | PASS locally | `cd backend && uv run python -m scripts.prove_system_status`; actual ATK + LAN + EVREN, NOT_SENT | Temporary protected risk-service HTTPS exists; dashboard remains local |
| C2 UX | 5 | Tested local dashboard | 57 frontend tests; [System Status screenshot](evidence/system-status-verified.png), source modes and actual policy latency; on-chain card verifies Agent #273 and sample receipt | Jury UX judgment pending; no usability study |
| C3 Pitch and hard Q&A | 10 | PREPARED | [Pitch/Q&A](PITCH_QA.md), [existing deck](pitch/SLIDES_8_DECK.md) | Rehearsal/jury acceptance not measured |
| D1 Working deployed product | 5 | PARTIAL | Local FastAPI/Next product and deployed Fuji contracts; [real temporary HTTPS proof](../backend/evidence/public-service-http.json) | Temporary protected HTTPS health and assessment passed; permanent hosting and independent-device check missing |
| D2 Architecture quality | 5 | PASS checks | 208 isolated backend tests, 57 frontend tests, 3 EVM tests; frozen API check; measured public service calls actual Python policy | Prototype single-worker key/limits, indefinite retention; not production certification |
| D3 Technical difficulty | 5 | Demonstrated implementation | Official MCP stdio discovery/call, argv-only CLI, typed model boundaries, durable atomic intent/run budget, safe UNKNOWN handling, chain readback | No unsupported advanced-chain/model-performance claims |
| E1 C-Chain/L1 deployment | 5 | PASS, Fuji C-Chain | [Proof report](../web3/PROOF.md), actual contract `0x5ae5642cd6a02e0834b3fba822d442429aeadc5f`, identity #273 | Fuji testnet, not mainnet/runtime-on-chain |
| E2 Avalanche strengths | 5 | Receipt lifecycle demonstrated | Issue digest → confirmed real receipt → independent stored digest/owner verification; actual gas/fees in [manifest](../web3/fuji-proof-manifest.json) | Confirmation latency NOT_MEASURED; custom L1 and interchain messaging NOT_USED; scoring belongs to jury |
| F1 Official OKX agent tooling | 5 | PASS | `backend/evidence/system-status-http.json`: actual ATK market/MCP/TR evidence; packages 1.4.8; [ATK guide](atk/evidence.md) | Exchange DEMO order submission/reconciliation NOT_TESTED; no live order |
| F2 Could be an OKX.AI service | 5 | POSSIBLE / NOT_LISTED | [Authoritative-source requirements](product/OKX_AI_LISTING_READINESS.md); concrete authenticated advisory API | Temporary HTTPS + official wallet login/ASP eligibility passed; durable endpoint, registration/review and marketplace auth compatibility missing; x402 not implemented |

Maximum weights: **25 + 20 + 20 + 15 + 10 + 10 = 100**. No earned-score total is asserted.

## Measured latest sample

Real HTTP run `18d805b920bf4fcda861f51a9e5423db` used real BTC-USDT public ATK input, LAN model version `aegis-laya-base-f38a07fa01db` and EVREN `deepseek-v4.1-flash`. One cycle took **12.745448 seconds** from START to AUDIT event timestamps; the policy check measured **0.300 ms**. Sample count is **one**; this is not p50/p95 or an SLA. Models/ATK consumed most wall time. Real small-notional assessment returned UNAVAILABLE, oversize returned BLOCK, all with execution_authorized=false. Source is the JSON above, not a fabricated performance benchmark.

LAYA schema/transport/version passed, but legacy Observation lacks operational context and returns REVIEW/abstained=true. A separate synthetic complete-context LAN probe returned CONTINUE with confidence 0.0035. Neither establishes independent model quality or trade readiness. Person 2's reported 236 offline tests/dataset dry-runs are not re-labeled as model accuracy or backend E2E evidence. [Policy/mapping decision](product/LAYA_PERSON1_COORDINATION.md) preserves human labels and Python vetoes.

## Reproduce and inspect

```sh
cd backend
uv run pytest -q --junitxml=evidence/freeze-tests.xml
uv run ruff check aegis tests scripts
uv run python -m scripts.export_contract --check
# Existing local backend/frontend must be running, credentials stay in ignored local files:
uv run python -m scripts.prove_system_status
uv run python -m scripts.verify_models --evren-features --laya
uv run python -m scripts.prove_model_safety --replay evidence/model-safety.json
```

From `frontend/`: `npm run build`, `npx vitest run`, `npx tsc --noEmit`. From `web3/`: `npm test`; read-only chain commands are in `web3/README.md`. Recorded proof replay makes no network call; fresh provider probes do, consume bounded request budgets and may fail safely on timeout/429.

Offline safety traces are explicitly [OFFLINE_BACKEND_TEST](../backend/evidence/laya-offline-safety.json): pre-submit read timeout vs ambiguous submission, ACK/live/partial vs terminal status, duplicate/retry, permission revocation, stale/future, missing approval and safe no-trade. Fixture-derived events are not independent real exchange incidents. Network/process guards prevent real connections/submission in these tests.

## Deployment and source freeze

Latest upstream main was merged early at `36ee0cdfbfc5ec70f79a23052cf2a52b39ef8cc0`, including Person 2 source changes and frontend state improvements. No Person 2-owned ML source was edited by Person 1. Core and evidence commits are on `codex/person1-laya-coordination`; this is not an assertion that main has been updated. Remaining unrelated provider evidence was preserved, not overwritten.

Public artifacts that actually exist: [metadata](https://gist.githubusercontent.com/giraykirim/367b45ff5fce169bf1e7a1447eb88d91/raw/agent-registration.json), [identity transaction](https://testnet.snowtrace.io/tx/0x7b61d86a11c815b301d44d6062c938bd7c8995c9d81332f9bb476c0bc436f08b), [HALT receipt](https://testnet.snowtrace.io/tx/0xcb226fb049a7052ca8889d585dfcb3a1cf66528e318a60c7ff2c9b43a67de2f1). A temporary restricted HTTPS service exists at https://tears-forms-inexpensive-geometry.trycloudflare.com ([actual checks](../backend/evidence/public-service-http.json)); no public dashboard or OKX listing URL exists. Metadata continues to advertise no public service.

Latest exchange readiness: `uv run python -m scripts.prove_exchange_readiness` performed only official public/forced-demo read operations, with a hard operation allowlist. Authenticated demo account read PASS, account_known=true. Actual LAN LAYA returned REVIEW/abstained=true. Final gate vetoes: approval_unavailable, laya_not_clear, excess_exposure. Demo submission/readback remain NOT_TESTED; no private account values were exported. See `backend/evidence/exchange-readiness.json`.

OKX.AI: official onchainos 4.6.4 installed and owner completed login; actual ASP pre-check allows creation. `backend/evidence/okxai-onboarding.json` excludes account identifiers, email and credentials. No registration, listing approval, payment, or chain write occurred. Draft and remaining QA blockers are explicit in `product/OKX_AI_REGISTRATION_DRAFT.json`.

Fresh capability diagnostics at 14:20 UTC: EVREN discovery PASS, structured-output FAIL after the configured 15-second deadline, tool calling PASS, LAYA transport/schema PASS. `backend/evidence/models-feature-timeouts.json` preserves the earlier two 10-second timeouts. These are feature probes, not production-proposal or model-quality evidence; the earlier real NO_TRADE cycle remains a separate successful observation. No returned model tool was executed.

Final source integration merge: `af081c7d9407d4f1f8a88a7bd237850f7d558fc6` includes upstream main `254773a` (P2 policy-v2 and quarantined training reports only). Person 1 did not modify ML sources or promote a checkpoint. P2 reports 161/161 human-label agreement under v2 and 249 offline tests; those are source-reported results, not independently rerun backend/model-quality evidence. Their note explicitly preserves current live base and abstention envelope. The additional intent+unknown-flag REVIEW rule is conservative; final Python stale/future/approval/order vetos remain unchanged.

Browser proof: [actual live risk-service response](evidence/risk-service-live.png), `backend/evidence/risk-service-ui.json`. Same ID with changed intent produced a visible 409 explanation; original inputs restored the original response. A SHA-256 digest is a hash, not a cryptographic signature. The notional response contains nine explicitly specified fields; earlier prose calling it ten was corrected without changing the frozen schema.
