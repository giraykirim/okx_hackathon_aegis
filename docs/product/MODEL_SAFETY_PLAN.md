# Prompt 00A model and safety implementation plan

Goal: preserve the working backend, frozen Event/Decision/API shapes and genuine ATK transport while adding bounded model integrations and durable per-run budgets. No ml/**, frontend or web3 edits.

Baseline: 137 executed Python tests passed. Actual public ATK/MCP observations and NO_TRADE already work. No local EVREN key/model or LAYA URL is configured; authenticated model features and private TR demo remain NOT_TESTED.

1. Add regression tests for environment aliases/caps, missing or UNAVAILABLE LAYA/version mismatch, EVREN 429/malformed output, separate structured/tool probes, request budgets and malicious tool data. Run red, then implement settings/transport changes. Preserve the v2 classification label vocabulary by mapping wire UNAVAILABLE to REVIEW+abstention with explicit Event.details metadata.
2. Add sanitized model tool_call evidence with measured times/status/hashes, correlation IDs and version/model metadata. Never publish provider bodies or hidden reasoning. Validate structured proposals; do not execute model tools. Account discovery and optional feature probes are separate capabilities.
3. Test and add SQLite atomic per-run order/notional reservation alongside existing intent claim. Revalidate corrupt inputs and the explicit BTC-USDT allowlist at the final Python gate. Retain forced-demo interlocks, STOP behavior, unknown-state blocking and no placement retry.
4. Capture replayable real-ATK NO_TRADE and explicitly injected MOCK stale/duplicate HALT scenarios with complete phase/event/correlation evidence. Optional private demo stays NOT_TESTED unless independently verified; no private demo order is required or attempted here.
5. Run the complete Python suite with JUnit output, lint/format, frozen contracts and a backend HTTP smoke. Update the README with exact environment/discovery/probe/demo/replay steps. Review before publication. Preserve all existing functionality and running dashboard connectivity.
