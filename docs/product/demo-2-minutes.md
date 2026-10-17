# Two-minute demo — local backend, honest boundaries

Before the demo, from `backend/`: install locked dependencies, run `uv run python -m scripts.init_local`, and start the single-worker loopback server as in the README. Keep `.env`, shell variable values and auth headers off screen. Run verification first. This runbook does not stand in for Person 3's dashboard/public deployment.

| Time | Show / say | Concrete proof |
|---|---|---|
| 0:00–0:15 | “AEGIS is an operational pre-trade check for teams building trading agents. Models can abstain; deterministic policy retains execution authority.” | GET `/api/v1/service`; separate assessment-only scope, no trading authority |
| 0:15–0:45 | Start one autonomous run with `uv run python -m scripts.http_smoke`. No per-step prompts follow. | Actual backend observe → classify/fallback → reason/fallback → policy → NO_TRADE → audit; persisted events and SSE resume |
| 0:45–1:00 | Open the saved HTTP evidence or event timeline. Point to MARKET_ONLY and tool_call (MCP), or ATK_RECEIPT (legacy CLI). | Official MCP discovery/call or CLI argv, run ID, measured timestamps/duration and SHA-256; no claim of demo execution |
| 1:00–1:30 | Run `uv run python -m scripts.prove_service` once. Show the oversized intended action's HALT. | Real service calls fetch their own ATK data, reject caller trust flags, return false order permission and make zero trading decisions/orders |
| 1:30–1:45 | Show the small intent's partial check, unknown account context and declared model availability. | REVIEW or a justified market HALT; never label missing LAYA/EVREN as a trained or authenticated success |
| 1:45–2:00 | Show evidence manifest, target buyer and proposed pricing. State remaining deployment/model/on-chain gaps. | Frozen v2 + additive schema, reproducible tests, NOT_LISTED and NOT_TESTED entries; no self-awarded score |

If networking fails, show the captured failure status or a previously timestamped evidence file and identify it as recorded evidence. An offline MOCK run is a separate labeled fallback, not a real exchange demo. Do not modify market timestamps or account facts to force a green outcome.

Person 3 may replace the last segment with actual Fuji issue → confirm → verify only after deployment and independent read-back are complete. Show real transaction/chain/contract/digest and measured latency/fee evidence; until then, say NOT_TESTED. There is no on-chain Python/LLM execution claim.
