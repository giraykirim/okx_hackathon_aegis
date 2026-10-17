# AEGIS — operational safety checks for trading agents

**Buyer:** teams running trading agents, agent-platform operators, and developers integrating automated exchange workflows. The initial buyer is a small engineering team that needs explainable controls without building its own complete risk/audit service.

**Pain:** an agent can repeat an uncertain order, act on stale market data, treat a model response as permission, or leave an incident without enough evidence to reconstruct what happened. A model's confidence cannot establish account balances, venue execution status or policy compliance.

**Proposed value:** a reusable pre-trade operational check plus a self-monitoring reference agent. AEGIS separates observation, operational classification, bounded analysis, deterministic policy, action/no-trade, verification and audit. It returns reason codes, correlation/evidence IDs and a policy version. A recorded HALT digest is independently anchored on Fuji and AEGIS is registered as Agent #273. These records do not certify model correctness.

**What exists:** a tested FastAPI/SQLite backend, autonomous MOCK NO_TRADE/HALT timelines, persisted order uncertainty/idempotency, real official ATK market observations, authenticated assessment endpoints, SSE and frozen integration schemas. The new notional request returns `execution_authorized=false`. Without trustworthy account data, it returns UNAVAILABLE or BLOCK, never optimistic ALLOW. Caller context is ignored and credentials/private balances are prohibited. A separate MOCK mode is explicit about unavailable real data. LAYA and EVREN have not been certified by the MOCK demo.

**Pricing hypothesis:** USD 0.01 per assessment or USD 99/month for a team tier with 10,000 assessments and audit export/support. These are experiments, not live pricing, customers, payments or revenue. Unit costs, authenticated model latency and willingness to pay still need measurement. This is an operational checkpoint, not a high-frequency trading feed or investment advice.

## Thirty-day go-to-market experiment

| Days | Experiment | Measure / decision |
|---|---|---|
| 1–7 | Interview five prospective trading-agent teams about unsafe retries, stale state and audit gaps; request consent before reviewing redacted examples. | Record actual incident patterns and integration requirements. No clients are claimed yet. |
| 8–14 | Let interested developers replay supplied MOCK fixtures and synthetic failure cases through a small integration example. | Measure integration time, veto explainability and false-positive complaints; all synthetic inputs remain labeled. |
| 15–21 | Invite up to three consenting teams to a sandbox pilot after access controls and a real host are ready. | Measure actual availability, p50/p95 latency, cost per check and duplicate/unsafe requests blocked. These are targets, not results. |
| 22–30 | Test per-call versus team-subscription offers; interview teams that decline or stop using the sandbox. | Continue only if teams repeatedly use the checks, find the reasons useful and show willingness to pay at sustainable cost. Report actual counts, including zero. |

Do not use profit or avoided-loss claims as a substitute for measured operational outcomes. Public runtime deployment, account-connected customer assessment, independent model benchmarks and billing remain unverified. Fuji identity and the recorded receipt are verified; see web3/PROOF.md. The current seven-day pilot and deployment/retention details are in SERVICE_OPERATIONS.md.
