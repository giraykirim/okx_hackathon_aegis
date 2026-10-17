# Frozen Person 3 integration bundle

Person 1 retains ownership of backend/contracts; no frontend, web3 or model files were changed. There is no Person 3 chat available. This versioned bundle and its GitHub publication are the handoff; no recipient acknowledgment is assumed.

- `openapi.yaml`: original frozen v2 contract, SHA-256 `a437caaa81ae590fc258aa0aeeb6498b1c38ec745483a701a4b2f0c66314d5ae`. All original routes, Event and Decision schemas are unchanged.
- `service-openapi-1.0.yaml`: byte-identical archive of the prior quantity-based service schema. That request/response remains supported.
- `service-openapi.yaml`: current service 1.1.0, with a union accepting either the new notional contract or the previous quantity contract. Do not mix fields from both forms.
- `frozen/aegis-v2-service-1.1.0.yaml`: exact combined runtime OpenAPI snapshot for type generation. It is frozen; future changes require a coordinated new snapshot version.
- `fixtures/`: explicit request fixtures and actual captured MOCK responses, with the reproducible curl command and source limitations.

Use the notional request `{request_id,symbol,proposed_action,proposed_notional,requester_context?}`. Amount is quote-USDT notional as a string; supported symbol is BTC-USDT and actions BUY/SELL/NO_TRADE. The response has `{request_id,verdict,execution_authorized,reason_codes,evidence_ids,evaluated_at,source_mode,policy_version,chain_receipt}`. Render UNAVAILABLE/BLOCK as such; never infer execution approval. The service does not know the caller's private account and never borrows the operator's balances. `chain_receipt=null` means no independently verified receipt.

Consume the v2 timeline without changing existing event types. Normalized phases are additive fields in `Event.details`: OBSERVE → CLASSIFY → REASON → RISK_CHECK → ACT/NO_TRADE → VERIFY → AUDIT. Existing `RISK_GATE` maps to RISK_CHECK, `EXECUTE` to ACT. `details.cycle_id` separates cycles within one run. STOP is latched/idempotent until START; an entire cycle has a configured deadline, and ambiguous submitted orders remain UNKNOWN and block new orders.

Keep `X-AEGIS-Key` and the separate operator control bearer token in private server configuration. Do not expose an unauthenticated frontend control proxy or put keys in browser code/screenshots. Coordinate the real origin before publishing URLs or registration metadata. The isolated demo runs only on loopback port 8001; the normal MARKET_ONLY server uses port 8000. No public deployment or receipt contract is claimed.

Validate with `cd backend && uv run python -m scripts.export_contract --check`. The frozen bundle's SHA-256 hashes are in `frozen/manifest.json`. MOCK proof is `backend/evidence/mock-contract-http.json`. The independent verification run, not this document, determines PASS/FAIL.
