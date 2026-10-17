# Person 1 / LAYA coordination decision — 2026-10-17

Decision: GO for existing fail-closed shadow/fallback monitoring; NO-GO for full-context runtime activation, training approval, model-quality approval or exchange execution. The base checkpoint is not a production-approved model. LAN schema compatibility and independent model accuracy are different claims.

Remote inspected by fetch only: `b949b19ef9fdf13cd38cb86b4e3963d5e4be609d`. Person 2's earlier backend snapshot is `d6ff7b7380de3f8be2a558174cb67211bae81acf`; Person 1 baseline is `ecd6d8dd97a19e50538d2deeb2db17e222b4c187`. No pull, merge, reset, rebase or overwrite was performed. The unrelated dirty frontend, web3 and provider evidence files remain untouched by this task's commits.

## Human labels and deployed policy

`contracts/laya-trusted-context-v1.json` records all five exact group IDs and the twenty source case IDs from Person 2's pushed `ml/policy_alignment/v2-r169-step1/evidence.json`, plus original scenario/source/trace/capture grouping. Quantity variants and regenerated IDs are not independent incidents. No labels or ML files were edited.

| Original group | Members | Context | agreed_label | Revision |
|---|---:|---|---|---|
| 6035c658446bc766 | 4 | age 40, approval absent, intent | REVIEW | Person 2 ML operational-label revision required |
| b507903e784e923b | 4 | age -2.1, intent | REVIEW | Person 2 ML operational-label revision required |
| bd4f3224298b7c68 | 4 | age 15.1, intent | REVIEW | Person 2 ML operational-label revision required |
| c328abb0010e5796 | 4 | age 40, approval present, intent | REVIEW | Person 2 ML operational-label revision required |
| cb09120331fb2593 | 4 | no intent, permission_revoked=null | CONTINUE | Keep legacy behavior; reject unconditional proposed unknown-permission relabel |

The deployed ML reference remains `aegis-operational-v1`; it still returns HALT for known stale/future feeds. `aegis-human-preserved-coordination-v1` names this recorded agreement only, **not a deployed ML policy**. No ML revision commit or revision-test PASS exists. Four groups remain an explicit deployment mismatch until Person 2 versions and tests the change. A human REVIEW label means investigate/refresh while trading stays blocked. No-intent CONTINUE means monitoring only; null revocation is preserved as unknown, never converted to confirmed permission.

Python `aegis.policy.check` remains final. Stale >15s, future <-2s, missing positive approval, duplicate intent and unresolved journal entries all veto execution independently of a model CONTINUE. Twenty source cases are checked against that unchanged gate. The tests establish gate behavior, not learned model accuracy or label-policy implementation.

## Call order and trust boundary

Current runtime remains OBSERVE → CLASSIFY(Observation) → REASON → RISK_CHECK → ACT/NO_TRADE → VERIFY → AUDIT. The legacy HTTP envelope remains exactly `{state, run_id, correlation_id}` with five response fields `{label, confidence, abstained, model_version, latency_ms}`. Observation lacks required operational context, so the deployed LAN service correctly abstains. That fallback blocks trades.

Chosen target: **a separate post-proposal operational shadow stage**, after a typed EVREN proposal and trusted journal/policy reads. `aegis.laya_context.build_shadow_context` is a pure, inactive builder; no API or runtime invokes it. It emits only `state.operational` allowlisted facts, explicit nulls, missing fields and a separate unresolved diagnostic. Correlation/run IDs are HTTP transport only; credentials, account/order IDs, balances, intent IDs, free-form summaries and tool/news text never enter its model state.

Activation requires Person 2's mapping acknowledgment, policy version resolution and a tested backend caller. A syntactically complete caller assertion is not independently trusted data. We do not fill missing flags with false merely to get an inference answer. The existing envelope can carry the proposed state, but changing the runtime state semantics remains a coordinated step.

| Field | Actual source / computation time | Missing/null behavior |
|---|---|---|
| symbol | Validated Observation, after ATK observation | Invalid or unsupported rejected; no tool-text override |
| site | Settings.okx_site at context build | Configured routing intent only; does not prove regional/profile permission |
| source_mode | Settings.source_mode at context build | Only configured typed mode; never requester context |
| feed_age_seconds | UTC backend now minus Observation.observed_at at build | Signed age retained; invalid timestamps reject, never clamp future to fresh |
| intent_requested | Schema-validated Proposal.action after REASON | No proposal → null; only explicit NO_TRADE → false |
| quantity | Validated Proposal Decimal encoded as string | Missing proposal → null; no float conversion; not a filled quantity |
| account_known | Observation's explicit known-account flag | False means unavailable/unknown account; default zero balances are not proof |
| approval_available | Independent final execution readiness/control check | null until explicitly checked; demo_ready alone is not proof of remote profile permissions |
| api_timeout | Current-cycle bounded transport attempt outcomes | null if no complete attempt telemetry; distinguishes pre-submit read failure from submit ambiguity |
| agents_disagree | Trusted comparison of typed same-scope results, if implemented | Currently null: no reliable same-scope comparator implemented |
| unknown_order | Completed journal query: any UNKNOWN status | null if not queried; PENDING ACK is unresolved but is NOT unknown submission |
| duplicate_intent | Store.duplicate(proposal.intent_id), after proposal, under transaction/claim protection for actual execution | null before query/proposal; never an LLM assertion |
| permission_revoked | Independently observed revoke/control transition | Currently null without revocation telemetry; missing configuration is not proof of revocation |
| injection_detected | Independently checked security finding, not untrusted text or a model assertion | Currently null unless an explicit validated detector/test injection supplies it |
| deployment_integrity_failure | Independent checkpoint/deployment integrity verification | Currently null; health/model version alone is not a cryptographic integrity check |
| excess_exposure | Deterministic Decimal gate/precheck with current known account snapshot and bounded sizing | null until that computation is available; no private amounts sent to model |

`PENDING` (ACK/live/partial) and `UNKNOWN` both block new orders but have different meanings. Filled, canceled and mmp_canceled are verified terminal statuses; VERIFIED does not imply filled. Ambiguous submit gets readback only, never blind placement retry. Existing runtime rechecks permission after reasoning and respects STOP; the new mapper grants no authority.

## Reproduce evidence

From `backend/`:

```sh
AEGIS_OFFLINE_PROOF_PATH=/tmp/aegis-offline-safety.json uv run pytest -q --junitxml=/tmp/aegis-laya-isolated-tests.xml
uv run ruff check aegis/laya_context.py tests/conftest.py tests/test_laya_coordination.py tests/test_laya_safety_proof.py scripts/probe_laya_lan.py
uv run python -m scripts.export_contract --check
# Separate explicit network test; uses only synthetic public fixtures, never keys/orders:
uv run python -m scripts.probe_laya_lan
```

The pytest guard disables `.env` before module collection, removes inherited provider settings for each test, and denies real socket connects and process spawning. Individual tests inject local transports. `backend/evidence/laya-offline-safety.json` is labeled OFFLINE_BACKEND_TEST, strips account/order/run IDs and raw logs, and retains stable scenario/source/derivative grouping. It must not be presented as real ATK output. The LAN probe writes `/tmp/aegis-laya-lan.json`; its separate evidence artifact includes actual HTTP requests/responses, with synthetic prices/flags clearly identified.

The first unisolated full pytest run exposed a pre-existing Settings() test reading local `.env` (189 pass, one failure). No exchange submission occurred; the test guard fixes that isolation defect. One third-party Starlette/AnyIO deprecation warning remains. This report approves neither independent data, human annotation quality, training nor a production model.

Final executed result: **191 passed**, 1 third-party warning, 1.60s; lint and frozen contract check PASS. The real backend `Models.classify` adapter was also called over LAN with a synthetic Observation: expected version, REVIEW, abstained=true and validated transport; this does not establish full-context inference or model accuracy. Implementation commit: `4ff56b7fcfb031f988cd61dd63af89b21953f12a`.
