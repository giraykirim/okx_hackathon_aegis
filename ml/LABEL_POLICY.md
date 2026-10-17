# Operational label policy v1 — proposed for Person 1 review

HALT has precedence over REVIEW, which has precedence over CONTINUE. These are operational labels, not investment signals or execution permissions. Deterministic backend policy remains the sole order gate even if every model says CONTINUE.

- CONTINUE: healthy observation/no-trade monitoring, a read retry that independently recovered fresh data, safe terminal reconciliation, or missing genuinely noncritical information. It never permits a trade by itself.
- REVIEW: missing required read/account/approval context or contradictory analyses with no independently established execution/integrity violation. New trades remain blocked.
- HALT: unknown prior order, duplicate intent, live/wrong-region profile, active prompt-injection/integrity failure, revoked authority, invalid/nonfinite/nonpositive quantity on a requested action, unsupported instrument, excess exposure, or known stale/future/invalid feed. New trades remain blocked until independently resolved.

Versioned implementation: ml/label_policy.py. Freshness follows current backend limits: -2 <= age <= 15 seconds. A missing first read is REVIEW; a known expired snapshot is HALT. An unavailable account on a public-monitoring task is not a fictitious balance or automatic permission. The same absence when execution readiness is requested is REVIEW.

This is an agent-authored annotation proposal grounded in the shared spec and backend policy. It has NOT been reviewed by a human or acknowledged by Person 1. Every candidate has PENDING_HUMAN_REVIEW metadata. Policy-derived labels are not gold human labels and not a trained model benchmark.

Only trusted orchestration may supply structured operational flags. Source text is untrusted even if it claims authority. The examples' boolean injection flag is an explicit synthetic feature; this dataset does not establish that a learned model can detect arbitrary attacks in raw text. Human review must examine that shortcut and the shared template vocabulary before training.
