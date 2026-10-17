# Spot lifecycle candidate dataset — NOT TRAINING APPROVED

Version spot-lifecycle-candidate-v1. 720 synthetic-derived rows: 240 CONTINUE, 240 REVIEW, 240 HALT. Twelve order types, two sides, fifteen scenario families, two variants. ONE original public market capture; variations are NOT independent real trade incidents.

Source: instruments and BTC-USDT orderbook from data/atk_spot/20261017T102105Z (see source_mapping.json for exact paths/hashes and official documentation). All private-response-shaped fixtures, account/permission/approval facts and execution timelines are SYNTHETIC. No private endpoint called, no order sent, no real account or credential read. Real market prices/precision anchor scale only, not fill probability or profitability. OKX_DEMO in the input is hypothetical offline replay context, not an actual demo exchange run.

Official LAYA state/questions/expected format. Labels come from independent proposed rules, NEVER LAYA's prediction. Metadata preserves scenario family, source URLs, derivation and PENDING_HUMAN_REVIEW. API fields are sanitized subsets, not full validated round-trip private responses; availability of private/algo features on this site/account is UNVERIFIED.

No split produced: keep the whole source capture and all related variants grouped together. Independent sources/families and real anonymized backend/demo execution traces are required before choosing grouped train/validation/calibration/final-test splits. Existing datasets unchanged. The 720 rows were all scanned diagnostically and cannot now be claimed as untouched final evaluation data.

Use human_review.csv for actual review; never automatically mark approval. lifecycle_review_gate.py refuses export until all rows have actual review fields. Candidate schema success and balanced class counts do NOT establish realism or oracle correctness. The proposed lifecycle oracle still needs Person 1 agreement; no backend contract or deployed policy changed.

Current base model diagnostic: 240/240 HALT candidates predicted CONTINUE; no input truncation. NOT a held-out or human-gold score. Model remains shadow-only, with deterministic safety veto and no execution authority. See ml/TRADE-LIFECYCLE-REPORT.md for metrics, coverage gaps and controlled training/debug protocol. No fine-tuning run in this task.
