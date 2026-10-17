# AEGIS operational-state candidate dataset v1

Status: STRUCTURAL QA CANDIDATE; NOT HUMAN-REVIEWED, NOT TRAINING-APPROVED. No fine-tuning, inference benchmark or model evaluation was run in P2-01. It is not a price predictor or a guarantee of safe/profitable trading.

## Composition

80 base rows across 20 scenario groups, plus 12 compound HALT challenge rows. Rather than expand templates to reach 300–700, this version retains a small inspectable seed set. It is still synthetic and cannot establish real-world generalization.

| Split | CONTINUE | REVIEW | HALT | Total | Groups |
|---|---:|---:|---:|---:|---:|
| train | 12 | 12 | 32 | 56 | 14 |
| val | 4 | 4 | 4 | 12 | 3 |
| test | 4 | 4 | 4 | 12 | 3 |
| challenge | 0 | 0 | 12 | 12 | 1 |

Base group split is exactly 70/15/15; base row split is also 70/15/15. Class balance differs across splits: train intentionally contains more distinct HALT families. No checkpoint has seen the test or challenge set; generation/schema/hash QA is not model evaluation. Split assignments are frozen in the builder, not optimized against predictions.

The 76 synthetic rows comprise 68 policy examples and eight incident-inspired examples. Four additional rows are derived from genuine public backend ATK receipts, all from one local capture/session and assigned to train together. Their operational readiness labels are agent-derived, not human gold labels or actual observed incident outcomes. Timestamped sanitized receipt evidence and original capture SHA-256 are retained separately.

All paraphrases within each declared scenario family stay in one split. All examples derived from a given incident source stay together. The entire local ATK capture is one group. The 12 challenge cases combine unresolved order state with different additional hazards, kept outside train/val/test.

## Format and provenance

Each JSONL line contains exactly state (a JSON string), questions (one choice question), expected (operational_state label). Source, rationale, group, split, line number, hashes and review status live ONLY in metadata.csv; labels/rationales are not added to state.

Official format reference: https://github.com/NandhaKishorM/laya/blob/main/docs/finetune.md
Question schema is in ml/label_policy.py. Sources and narrowly documented facts are in sources.json. Published incident facts are SOURCE_DOCUMENTED there, but every translated training case is SYNTHETIC_DERIVED in metadata. Neither source author supplied our labels.

Parallel FindAll was unavailable in this session. Research used primary-source web retrieval of the SEC Knight Capital release and Cloudflare's own 2019 outage postmortem instead. This source-method requirement remains a disclosed deviation, not a fabricated FindAll result.

No person has manually reviewed these rows. All human_review_status values are PENDING_HUMAN_REVIEW; reviewer/reviewed_at are empty. The manual-review provenance requirement is therefore NOT COMPLETE. The quality gate with --require-human-review intentionally fails.

## Limits and risks

- Human-reviewed policy-grounded examples are still required; generated rule labels cannot substitute for expert annotation.
- The structured flags and shared templates make this partly a rule-imitation dataset. High future scores may reflect shortcuts, not incident understanding.
- Family/source separation blocks declared paraphrase/incident leakage but does not prove semantic independence; no embedding-based near-duplicate audit was run.
- The tiny test set has low statistical power and covers unseen families, not all training failure families. A 100% result would not prove production reliability.
- Challenge recombines familiar hazards; it is not an independent external incident benchmark. Report HALT-to-CONTINUE count and denominator, abstention/coverage and per-class confusion later, alongside accuracy and calibration.
- Public ATK data do not establish private balances, approvals or order states. Nothing here licenses account readiness inference from public quotes.
- Training state enrichment is not yet acknowledged by Person 1; see ml/PERSON1-HANDOFF.md. Do not deploy this mapping as an agreed API.
- No checkpoint weights were downloaded, trained or published. No measured ML latency, accuracy or trading performance is claimed.

## Reproduce on this machine

From the repository root, use the pre-existing sibling GPU Python environment:

```powershell
..\aegis\.venv\Scripts\python.exe scripts/ml/check_environment.py
..\aegis\.venv\Scripts\python.exe scripts/ml/build_dataset.py
..\aegis\.venv\Scripts\python.exe scripts/ml/qa_dataset.py
..\aegis\.venv\Scripts\python.exe scripts/ml/test_dataset.py
# Expected nonzero exit until genuine human review is supplied:
..\aegis\.venv\Scripts\python.exe scripts/ml/qa_dataset.py --require-human-review
```

Builder reads only the named public backend evidence file and writes owned data paths. Generation recreates the candidate snapshot and does not preserve later manual changes; freeze/copy reviewed annotations as a new version before regeneration. manifest.json hashes data/source/policy/builder versions. A changed capture changes dataset hashes; preserve the original capture for reproducibility. qa_report.json reports schema, exact duplicates, declared source/family isolation, review provenance, source support, hash integrity and distributions. Official installed LAYA Dataset.from_jsonl compatibility is tested without a checkpoint.

## Cleanup

P2-01 installed no dependencies and changed no system settings. After backup, remove only the task-created ml/, data/ and scripts/ml/ files if no teammate additions exist. The old GPU Python environment belongs to the earlier machine-preparation work and is reused unchanged. Never delete these directories blindly once teammates have added work.
