# OKX.AI listing readiness — checked 2026-10-17

**POSSIBLE candidate; NOT_LISTED; no submission or approval claimed.** AEGIS is a structured advisory API for trading-agent teams. A free A2MCP sandbox is the closest initial fit. Per-call and subscription amounts are commercial hypotheses, not configured marketplace billing.

Official sources reviewed:

- [ASP overview](https://web3.okx.com/onchainos/dev-docs/okxai/asp-introduction): providers can offer A2A or A2MCP services; identity, service information and platform review precede listing. A Fuji ERC-8004 token does not establish an OKX provider identity or approval.
- [A2MCP guide](https://web3.okx.com/onchainos/dev-docs/okxai/howtomcp): a free endpoint returns a direct result; paid calls use an x402 challenge/payment/replay flow. Both require a reachable public HTTPS domain and an endpoint self-check. The guide describes a callable API; it does not require inventing an MCP server or listing API.
- [ASP registration](https://web3.okx.com/onchainos/dev-docs/okxai/registerasp): Onchain OS/Agentic Wallet onboarding, provider registration with name/description/price/endpoint, then listing review. The official CLI login and read-only ASP pre-check now passed; provider creation and listing have not been submitted. Published review-time guidance is not an acceptance guarantee.
- [Payment SDK reference](https://web3.okx.com/onchainos/dev-docs/payments/sdk-overview): HTTP payment middleware is a separate integration. No SDK/payment settlement has been installed or tested for AEGIS.

| Requirement / readiness item | Status | Actual evidence or gap |
|---|---|---|
| Programmatically callable structured capability | VERIFIED | FastAPI POST `/api/v1/risk/evaluate`; string Decimal request and typed advisory result; `backend/evidence/system-status-http.json` |
| Clear service name, scope, input/output and limitations | VERIFIED | GET `/api/v1/service`; `contracts/service-openapi.yaml`; service never authorizes orders |
| Deterministic useful result with real provenance | VERIFIED | Server-side official ATK public facts feed the actual Python policy gate; hard vetoes and unavailable account data are distinguished |
| Separate caller authentication and deployment limits | VERIFIED | X-AEGIS-Key; one assessment at a time, six/minute, body/deadline bounds; prototype single-worker scope |
| Public server and HTTPS domain | PREPARED; owner deploy pending | `backend/Dockerfile` (Python + Node, official ATK CLI) and `backend/fly.toml` (Singapore, volume-backed SQLite audit). Image built and smoke-tested locally: official ATK market observation, key-less 200, keyed no-key 401, control 404. Vercel rejected: its Python runtime cannot spawn the ATK Node CLI |
| Public endpoint HTTPS self-check | VERIFIED from operator HTTPS client; independent device NOT_TESTED | Public health/descriptor 200, keyed evaluation 200, no-key 401, private controls 404. Web fetch tool could not access the temporary domain |
| Free endpoint marketplace authentication handoff | IMPLEMENTED | OKX A2MCP guide documents only free HTTP 200 or x402 402; no provider-key forwarding. `public_app` serves opt-in key-less `POST /api/v1/a2mcp/risk/evaluate` (`AEGIS_SERVICE_PUBLIC_TIER=true`, 3/min shared bucket, client keys stripped, MARKET_ONLY only). Keyed route and frozen contracts unchanged |
| Onchain OS / Agentic Wallet login and eligibility | VERIFIED | Official onchainos 4.6.4 checksum-verified install, login completed by owner; wallet status loggedIn=true; agent pre-check --role asp returned canCreate=true, aspCount=0; sanitized `backend/evidence/okxai-onboarding.json` |
| Actual OKX provider identity and submission | MISSING | No provider ID, listing URL, submission response or review notification exists; concrete draft is `OKX_AI_REGISTRATION_DRAFT.json` |
| Initial listing price/service endpoint | MISSING | Free pilot is proposed; no marketplace entry is configured |
| Paid x402 challenge, replay and settlement | NOT_APPLICABLE | Not needed for a proposed free pilot; MISSING for a paid launch. `x402Support=false` remains truthful |
| A2A negotiation/delivery/subscription operations | NOT_APPLICABLE | No negotiated-delivery agent is implemented; selected candidate is A2MCP |
| A2A/agent-card standard endpoint | NOT_APPLICABLE | OKX A2A service type is not proof that a separate agent-card protocol is implemented; no speculative card is published |
| Public ERC-8004 metadata | VERIFIED | [Actual descriptor](https://gist.githubusercontent.com/giraykirim/367b45ff5fce169bf1e7a1447eb88d91/raw/agent-registration.json); Fuji Agent #273. `services=[]`, `active=false` avoid advertising a transient, independently unverified runtime as a stable service |
| API reference inside ERC-8004 metadata | MISSING | Add a service reference only after the real endpoint is published and independently fetched |
| Tenant provisioning/revocation, distributed quotas, SLA | MISSING | Pilot uses a single deployment credential; production tenancy and SLA are not implemented |
| Independent security/model-quality validation | MISSING | Failure tests and base-model LAN transport do not prove model accuracy or production security certification |

Next gates: owner runs `fly deploy` + independent HTTPS self-check, real avatar, provider creation and review. The verified CLI create help requires an avatar and exactly four A2MCP description lines (capability, parameters, method, working curl); draft follows that shape but is explicitly unsubmitted. Do not send the temporary endpoint through QA while unauthenticated self-check returns 401. Login eligibility is not registration. Preserve `NOT_LISTED` until a verifiable listing exists. Never claim that POSSIBLE means accepted, approved or revenue-generating.
