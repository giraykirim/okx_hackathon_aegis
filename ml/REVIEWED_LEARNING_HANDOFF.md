# Backend / reviewer handoff — NOT ACKNOWLEDGED

The positive control passed. Real-task learning is BLOCKED until a new backend commit,
trusted-context agreement, independent traces and actual human review are available.
No automatic git pull/merge is implemented. Preserve the dirty worktree and coordinate with Person 1.

## Next input from Person 1

Provide the backend commit hash, confirm context mapping, and run core spot offline tests
with external networking and order submission disabled. Export ONLY sanitized contextual
facts from those executions. Offline fixtures are not real exchange responses. Never export
an .env, provider stderr, token, user/account ID, order ID, credential config or raw auth log.

Supported scope: BTC-USDT/cash spot, market/limit/post_only/FOK/IOC. Required scenario
coverage: no-trade, healthy monitoring, before/after-submit timeout, duplicate intent,
revoked permission, stale/future data, missing approval, partial fill, ACK versus verified
terminal state. FOK cannot partially fill. No claim of site/account behavior without evidence.

Existing /classify HTTP envelope remains untouched. The helper below is a PROPOSED inner
representation and does not deploy an adapter. Person 1 must map trusted context explicitly.
Missing execution facts must never be inferred from price or defaulted to false. If unavailable,
the eventual service must return REVIEW/abstained=true; report the scope mismatch instead of
pretending a full integration. Model CONTINUE never substitutes for execution approval.

## Bundle contract

Create a NEW task-owned directory under data/reviewed_learning/<bundle-id>. Do not reuse
debug_learning or the 720-row capture as independent final-test data.

Provide draft_cases.json with exactly 120 real, independently reviewed candidate inputs,
not 120 clones. Each draft case contains:

- case_id: opaque pseudonymous review identifier, no label or personal identifier.
- split: train / val / test, preassigned by a source-aware curator.
- origin: REAL_PUBLIC_CAPTURE / OFFLINE_BACKEND_TEST / SYNTHETIC_DERIVED.
- backend_commit: pinned 40-character commit hash.
- source_capture_group, source_event_group, parent_scenario_group: pseudonymous provenance
  groups. All relatives stay in one split; changing seed, clock or ID is not independence.
- context: exactly the fields accepted by state_from_context in scripts/ml/reviewed_learning.py.
  symbol=BTC-USDT, site=tr, source_mode=MOCK/MARKET_ONLY/OKX_DEMO; explicit intent_requested;
  quantity as numeric scalar; feed_age_seconds finite or null; account_known, approval_available,
  api_timeout, agents_disagree, unknown_order, duplicate_intent, permission_revoked,
  injection_detected, deployment_integrity_failure, excess_exposure each bool or null.

The origin classification describes evidence, not confidence. Unknown context stays null.
All model inputs use the same canonical serializer, with no candidate label/oracle reason.
Trace hashes bind exactly this sanitized context plus provenance. Raw private logs are not
needed and must not be included. Source authenticity and scenario independence require the
team's real attestations; JSON signatures here are content hashes, NOT proof of authenticity.

Provide backend_ack.json with EXACTLY these six fields, filled by the responsible teammate:

```json
{
  "person1_approved": false,
  "commit": "",
  "reviewer_role": "",
  "trusted_context_mapping_approved": false,
  "network_disabled": false,
  "order_execution_disabled": false
}
```

This example is intentionally blocked, NOT an actual acknowledgment. No one may have an
agent silently fill these fields as approved. No backend write or deployment is authorized here.

## Human review (60–90 minutes)

Use prepare-review to create blind_review.csv from the supplied cases. The view contains
only opaque case ID, model state and blank reviewer fields: no oracle or model answers.
Reviewer fills human_label, review_status=APPROVED, reviewer_role, reviewed_at_utc with
timezone and rationale. This is actual human work; generated unit-test approvals are not reviews.
Unresolved examples do not pass. After review, export-review emits approved/ with JSONL,
metadata, sanitized trace evidence and hash manifest. Every review still needs curator verification.

Required accepted counts: train60 (20/class), val30 (10/class), final test30 (10/class).
If honest source grouping or corrected labels cannot produce these counts, obtain new independent
cases. Do not clone, relabel merely for balance, or silently split one source incident across sets.
Do not promise these counts can be met in this hackathon window.

## Commands (existing GPU Python, repo root)

```powershell
python scripts/ml/reviewed_learning.py prepare-review data/reviewed_learning/<bundle-id>
# Human fills blind_review.csv; no automatic approval.
python scripts/ml/reviewed_learning.py export-review data/reviewed_learning/<bundle-id>
python scripts/ml/reviewed_learning.py validate data/reviewed_learning/<bundle-id>/approved --control ml/debug_learning/20261017T104341Z/result.json
python scripts/ml/reviewed_learning.py train data/reviewed_learning/<bundle-id>/approved --control ml/debug_learning/20261017T104341Z/result.json
```

The runner checks protected hashes, control success, all reviews, exact class/split counts,
source-group separation and bound trace hashes BEFORE starting training. It trains two head-only
eight-epoch seeds (17,29), micro-batch1/accumulation1/soft-CE, with a 30-minute limit per run.
It stops on nonfinite loss or OOM; full-encoder training is out of scope. New checkpoints stay
under models/reviewed_learning. Existing selected model is never overwritten.

VAL acceptance: zero HALT→CONTINUE, zero REVIEW→CONTINUE, CONTINUE recall>=.8,
macro-F1>=.8, all classes present, no invalid/truncated outputs. Selection uses VAL only;
final inference is guarded by an atomic one-shot marker. A failed/interrupted final test must
not be retried automatically or tuned against. Data schema/hash checks may read the final
dataset beforehand; no model predictions or selection use final-test examples before the gate.

Confidence is NOT treated as calibrated. The official small internal calibration split may warn;
it is not source-independent validation, and metrics on it must not be reported as final quality.
Ten final HALT examples are a very small pilot, not evidence of production safety.

These real-data paths are tested with artificial, temporary UNIT_TEST_ONLY fixtures only;
there has been no live backend end-to-end training run because actual inputs are not available.
