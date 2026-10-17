# P2-01 data and service coordination — ACKNOWLEDGMENT PENDING

Person 2 owns ml/**, data/**, models/** and scripts/ml/**. No backend, frozen contract, frontend or web3 file was edited in P2-01.

Existing service contract was read from contracts/openapi.yaml and backend/aegis/models.py:

POST /classify request: {state, run_id, correlation_id}
Response: {label, confidence, abstained, model_version, latency_ms}
Labels: CONTINUE / REVIEW / HALT. Confidence must be finite 0..1, latency finite nonnegative. Use REVIEW with abstained=true for unsupported/missing inputs; never manufacture a confident trained answer. Run IDs are correlation transport, not training input. Do not send credentials, control tokens or account identifiers to ML.

Current backend `state` is an Observation with price/feed/instrument/account fields. P2 candidate inputs use a deterministic JSON string with `operational` facts and `context`. The state/questions/expected *file format* is the official LAYA format; the inner operational enrichment is an AEGIS proposal, not an already agreed API amendment.

GAP TO RESOLVE WITH PERSON 1: Observation alone does not expose duplicate intent, unresolved journal state, revoked permissions, approval, source mode or tool-injection context. An eventual service must not infer those facts from price or silently default missing safety flags to healthy. Agree either on an internal trusted-context adapter or on a smaller model scope before P2-02/P2-03. Keep HTTP envelope unchanged; coordinate any added data through Person 1. No acknowledgment or cross-machine integration has occurred.

Review request: approve LABEL_POLICY.md precedence/boundaries; inspect data/metadata.csv source/family/review fields; decide trusted context mapping. Source incidents are synthetic derivations, not gold incident labels. Real ATK captures contain public observations only, never private accounts.

All 92 candidates require genuine human review. A reviewer should record actual identity/role, review time, label corrections and rationale in a separately reviewed annotation revision; the generator must not claim that review. Freeze revised dataset hashes, then train/calibrate on train/val only. The test split must not select checkpoints, thresholds or prompt wording. Challenge is a separate predeclared stress set, not an external independent validation set.
