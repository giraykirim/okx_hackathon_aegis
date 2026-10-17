# System Status and service readiness implementation plan

Goal: make existing integrations observable and callable, connect notional assessments to the actual deterministic gate, and freeze a truthful jury/demo package. No live orders, no ML edits, no invented public deployment or listing.

1. Preserve existing Fuji work and merge latest main early; manually retain upstream state helpers and verified wallet flow. Preserve unrelated dirty provider evidence.
2. Configure local LAYA URL/version only; keep MARKET_ONLY and demo flags false. Restart existing backend, run bounded real ATK -> LAYA advisory -> EVREN -> Python NO_TRADE -> STOP. Separate transport from model quality and diagnostic feature probes.
3. Add test-first checks that notional MARKET_ONLY requests invoke the actual gate, strip accidental account data, enforce server freshness/quantity precision and never execute. Keep response schema/frozen contracts unchanged and MOCK deterministic.
4. Add measured Python policy latency to Event.details only. Enrich frontend server snapshot with freshly verified Fuji capability; report transport, abstention, historic timestamps and execution-disabled state honestly. Remove fabricated latency. Test status derivation and BFF auth boundaries.
5. Verify official OKX ASP/A2MCP guidance. Document requirements with VERIFIED/MISSING/NOT_APPLICABLE; select possible free A2MCP pilot, no fabricated registration API, A2A card or payment integration. Do not change public metadata to advertise an unpublished API.
6. Provide deployment/access/privacy/retention and seven-day pilot runbook, sample authenticated curl and current response. No hosting account/domain exists; public API deployment remains MISSING. Provide reproducible protected deployment config, not an unauthenticated control proxy.
7. Run offline backend/frontend/contract tests, real local HTTP smoke and chain verification. Write 100-point rubric evidence matrix and >=12 hard Q&A, machine-readable measured freeze manifest and Person 3 contract handoff. Commit and push integration branch; create reviewable PR if useful. Do not merge to main without verifying all core tests.
