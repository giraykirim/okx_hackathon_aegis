# LAYA backend coordination implementation plan

Goal: pin backend behavior and provide a conservative Person 1 mapping decision, offline execution-isolated evidence and real LAN schema evidence within the requested initial 20 minutes.

Architecture: preserve {state, run_id, correlation_id} and current observation-only runtime/fail-closed fallback. Add a pure, inactive post-proposal shadow context builder with explicit nulls and no IDs/free text. Full operational inference remains NO-GO until Person 2 accepts mapping and policy revision. No edits to ml/**, data/** or frontend/web3. No merges/pulls/resets.

1. Inspect baseline SHA, remote refs and existing policy, journal/reconciliation and model adapters. Fetch objects only; preserve dirty files.
2. Add failing tests for typed field allowlist/null preservation, unresolved versus unknown submission, credential/text omission and human-label policy decision.
3. Implement minimal pure shadow context builder and versioned coordination contract; do not enable it in runtime or relax Python vetoes.
4. Add network/subprocess-denied offline safety proof covering pre-submit reads, ambiguous submission, duplicates/retry, revoked permission, freshness, approval, venue state and safe no-trade. Preserve scenario/source/derivative provenance; export no raw private data or IDs.
5. Run full backend pytest, lint and frozen OpenAPI checks. Pin selective implementation commit; record exact code SHA in evidence.
6. Probe LAN health, legacy Observation, unsupported state and clearly synthetic candidate operational state; validate exact five fields/version separately from model correctness.
7. Fetch Person 2 push without checkout; consume supplied response template/diff from git object when available. Fill evidence-backed response, with explicit missing-input blockers otherwise.
