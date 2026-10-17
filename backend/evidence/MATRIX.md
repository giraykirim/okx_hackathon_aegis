# Evidence matrix — 17 October 2026

Only evidence actually captured is marked PASS. JSON files include timestamps and source modes. Offline fake-transport tests are distinguished from external integration results.

The authorized rubric amendment uses 25/20/20/15/10/10 weights. The current machine-readable map is `jury-manifest.json`, with no self-awarded score. Local real-market assessment evidence is in `amendment-http.json`; standalone service 1.1 MOCK evidence is in `mock-contract-http.json` and `mock-curl.json`. Current executed test counts are in `tests.xml`/the manifest. The initial v2 schema remains frozen; additive service schemas are separate.

| Requirement | Status | Evidence / remaining dependency |
|---|---|---|
| Official ATK CLI and real backend MCP observation on TR | PASS | `atk-official.json`, `atk-terminal.txt`, `docs/atk/CAPABILITIES.md`: installed help/provenance, actual MCP tools/list + tools/call, public ticker + instruments, exchange timestamp, persisted NO_TRADE timeline |
| Model safety authority / bounded requests / replay | PASS — real public ATK + explicit MOCK + offline tests | `model-safety.json`: real NO_TRADE and synthetic stale/duplicate HALT with per-run/cycle/event IDs and hash-bound replay. `tests.xml`: model caps/cancellation, malformed/rate-limited providers, wrong quote, durable run budgets and STOP. Real account/feature access is separate in `models.json`. |
| Reusable risk assessment service | PASS — local real HTTP | `amendment-http.json`: separately authenticated service, server ATK provenance, exact commands/timestamps/hashes, REVIEW/HALT, no order permission or trading side effects |
| Caller trust flags / access and resource limits | PASS — offline and scoped HTTP proof | Spoofed account input rejected; separate key, rolling-minute limit, bounded body including ASGI prefix/chunked requests, single assessment and deadline |
| OKX.AI listing | NOT_LISTED | Official requirements researched; integration POSSIBLE, no submission/review/listing/payment verified |
| Initial v2 compatibility | PASS | Frozen SHA-256, all original paths/components; additive contract exported separately |
| New string-notional service / deterministic MOCK | PASS — actual HTTP/cURL and offline | Exact requested response, UNAVAILABLE/BLOCK with false authorization; null-safe untrusted context; cached correlation/conflicts/restart; legacy quantity form preserved |
| Complete normalized phase timeline / idempotent STOP | PASS — actual MOCK HTTP/SSE and offline | OBSERVE→CLASSIFY→REASON→RISK_CHECK→ACT/NO_TRADE→VERIFY→AUDIT in Event.details; no Event/Decision shape changes |
| Frozen Person 3 integration bundle / fixtures | PASS | contracts/frozen/manifest.json with exact combined schema and request/actual captured MOCK response fixtures |
| Autonomous real observation / safe NO_TRADE | PASS | `latest.json` and `http-smoke.json`: MARKET_ONLY ATK observation, fallback classify/reason, gate, persisted audit |
| Autonomous full simulated lifecycle | PASS — MOCK only | `latest.json`: start/stop, scripted inputs, approved MOCK fill, NOT_SENT, timeline and counts |
| Unsafe stale scenario veto | PASS — MOCK + offline policy tests | No execution call; reason `stale_feed`, NOT_SENT |
| Other hard vetoes / restart blocking / idempotency | PASS — offline | `pytest`: deterministic policy, atomic SQLite claim, persisted UNKNOWN, no placement retry |
| Price-bound submission / venue reconciliation | PASS — offline only | Fake venue validates cash IOC price cap, terminal/open states and mismatches; real demo still NOT_TESTED |
| Interrupted journal/final decision write | PASS — offline | SQLite abort-trigger regression proves atomic rollback |
| Bounded model input/output and transport | PASS — offline | Typed schema, no tool calls, disabled EVREN tools, oversize/trickled stream regression tests |
| EVREN public protocol | PASS | Retrieved actual public OpenAPI; TermsStatus accepted boolean; unauthenticated endpoint HTTP 401 |
| EVREN authenticated discovery/generation | NOT_TESTED | Needs local account API key, accepted terms and discovered model selection |
| LAYA LAN classification | NOT_TESTED | RTX service URL deferred by user; REVIEW/abstained advisory fallback |
| CUDA VRAM / LAYA fine-tuning benchmark | NOT_TESTED | Person 2 owns RTX machine and model training |
| Real OKX demo order / venue reconciliation | NOT_TESTED | No demo credentials or independent TR demo confirmation; zero exchange writes attempted |
| Shared v2 HTTP API / authenticated controls / actual SSE resume | PASS | `http-smoke.json` plus offline API tests; `contracts/openapi.yaml` generated and checked |
| Dashboard integration | NOT_TESTED | Person 3 owns frontend; backend snapshot/events ready, no frontend fabricated here |
| Fuji ERC-8004 identity / public registration JSON | NOT_TESTED | Person 3 owns wallet/registration; API verified=false and all proof fields null |
| PnL / profits | NOT_TESTED | Metrics deliberately report pnl=null |
| Organizer bonus criteria | NOT_TESTED | No organizer confirmation supplied |

Known test dependency warning: Starlette TestClient uses an AnyIO alias deprecated by the installed AnyIO release. It does not fail the tests; no warning was suppressed. `PASS` on capabilities means the named response was observed/validated, not total project completion.
