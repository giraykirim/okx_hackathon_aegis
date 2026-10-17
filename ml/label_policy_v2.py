"""AEGIS operational label policy v2 (human-preserved). Labels are never order permissions.

Implements the Person 1 coordination agreement recorded on branch
``codex/person1-laya-coordination`` (commits 4ff56b7 / da8d0c2, contract
``contracts/laya-trusted-context-v1.json``, agreement name
``aegis-human-preserved-coordination-v1``):

* A finite numeric feed age that is stale (> 15 s) or future (< -2 s) is an
  investigate/refresh condition -> REVIEW, not HALT. The four stale/future
  groups had human REVIEW decisions; Person 1 kept them. Person 2 (user)
  extended the same REVIEW semantics to no-intent stale/future cases so that
  an order intent never makes a label milder.
* No intent + ``permission_revoked=None`` stays CONTINUE (monitoring only).
  The proposed unconditional unknown-permission REVIEW rule was rejected.
  Null stays unknown; it is never converted into confirmed permission.
* With an order intent, an UNKNOWN (null) safety flag is REVIEW. v1 treated
  null as false and returned CONTINUE for 32 such human-REVIEW rows in the
  frozen v2-r169 bundle; the earlier 20-case audit only compared against the
  candidate rule, which already agreed, so these were never listed. This
  matches the human decisions and Person 1's "never fill missing flags with
  false" principle, and is strictly more conservative.

Unchanged from v1: integrity/authorization/execution flags, live/invalid mode,
wrong site, unsupported symbol, invalid quantity and NON-numeric/non-finite
timestamps remain HALT. Any HALT reason still dominates a stale feed.

This is a training/evaluation label reference only. It is NOT deployed in the
LAN service, does not change the selected checkpoint, and does not relax the
backend's deterministic Python execution vetoes (stale > 15 s, future < -2 s,
approval, duplicate, unresolved journal), which block trades independently.
v1 (``ml/label_policy.py``) is intentionally left byte-identical because
existing evidence bundles pin its SHA-256.
"""
import math

from ml.label_policy import LABELS, QUESTIONS  # identical model questions/labels

VERSION = 'aegis-operational-v2-human-preserved'
PARENT_VERSION = 'aegis-operational-v1'
STALE_AFTER_SECONDS = 15
FUTURE_BEFORE_SECONDS = -2
# Safety flags whose UNKNOWN (null/absent) value must not be read as "healthy" when an order is intended.
UNKNOWN_BLOCKS_INTENT = ('api_timeout', 'agents_disagree', 'unknown_order', 'duplicate_intent',
                         'permission_revoked', 'injection_detected', 'deployment_integrity_failure',
                         'excess_exposure')

__all__ = ['LABELS', 'PARENT_VERSION', 'QUESTIONS', 'VERSION', 'classify']


def _numeric_age(age):
    return isinstance(age, (float, int)) and not isinstance(age, bool) and math.isfinite(age)


def classify(facts):
    reasons = []
    for field in ('unknown_order', 'duplicate_intent', 'injection_detected', 'permission_revoked',
                  'deployment_integrity_failure', 'excess_exposure'):
        if facts.get(field):
            reasons.append(field)
    if facts.get('source_mode') not in ('MOCK', 'MARKET_ONLY', 'OKX_DEMO'):
        reasons.append('live_or_invalid_mode')
    if facts.get('site') != 'tr':
        reasons.append('wrong_site')
    age = facts.get('feed_age_seconds')
    stale_or_future = False
    if age is not None:
        if not _numeric_age(age):
            reasons.append('invalid_feed_timestamp')
        elif age > STALE_AFTER_SECONDS or age < FUTURE_BEFORE_SECONDS:
            stale_or_future = True
    if facts.get('symbol') != 'BTC-USDT':
        reasons.append('unsupported_symbol')
    if facts.get('intent_requested'):
        try:
            raw_quantity = facts.get('quantity')
            if isinstance(raw_quantity, bool):
                raise TypeError('Boolean is not a numeric quantity')
            quantity = float(raw_quantity)
            if not math.isfinite(quantity) or quantity <= 0:
                reasons.append('invalid_quantity')
        except (TypeError, ValueError):
            reasons.append('invalid_quantity')
    if reasons:
        return 'HALT', sorted(reasons)
    review = []
    if stale_or_future:
        review.append('stale_or_future_feed')
    if age is None or facts.get('api_timeout') or facts.get('agents_disagree'):
        review.append('missing_or_contradictory_context')
    if facts.get('intent_requested') and (not facts.get('account_known') or not facts.get('approval_available')):
        review.append('execution_context_unavailable')
    if facts.get('intent_requested') and any(facts.get(f, None) is None for f in UNKNOWN_BLOCKS_INTENT):
        review.append('safety_flag_unknown_with_intent')
    if review:
        return 'REVIEW', review
    return 'CONTINUE', ['monitoring_only']
