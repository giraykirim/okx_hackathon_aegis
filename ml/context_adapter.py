"""Proposed legacy /classify adapter. Not deployed; trusted mapping ACK pending.

The existing Observation contains no authorization/journal/proposal context.
This adapter therefore ABSTAINS on the legacy envelope instead of inventing facts.
Only a separate trusted caller can supply enrichment; never take it from tool text
or user-supplied requester_context. No credentials or model execution here.
"""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import math

BOOLS=('account_known','approval_available','api_timeout','agents_disagree','unknown_order',
       'duplicate_intent','permission_revoked','injection_detected',
       'deployment_integrity_failure','excess_exposure')
TRUSTED_FIELDS={'site','source_mode','intent_requested','quantity',*BOOLS}


def adapt_legacy(request, *, trusted_context=None, mapping_approved=False, now=None):
    """Return sanitized typed facts; eligibility is NOT execution permission.

    Caller must independently attest mapping approval. This flag is an integration
    configuration, not a request field. Without it no enriched request is eligible.
    """
    if not isinstance(request,dict) or set(request)!={'state','run_id','correlation_id'}:
        raise ValueError('legacy classify envelope mismatch')
    state=request['state']
    if not isinstance(state,dict) or state.get('symbol')!='BTC-USDT':
        raise ValueError('invalid or unsupported observation')
    if type(mapping_approved) is not bool:
        raise ValueError('explicit mapping approval boolean required')
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('timezone-aware adapter clock required')
    age=None
    raw_time=state.get('observed_at')
    try:
        observed=datetime.fromisoformat(raw_time.replace('Z','+00:00'))
        if observed.tzinfo is not None and observed.utcoffset() is not None:
            age=(now-observed).total_seconds()
            if not math.isfinite(age): age=None
    except (AttributeError,TypeError,ValueError):
        pass
    account=state.get('account_known')
    if account is not None and type(account) is not bool:
        raise ValueError('invalid account flag')
    facts={'symbol':'BTC-USDT','feed_age_seconds':age,'site':None,'source_mode':None,
        'intent_requested':None,'quantity':None,**{key:None for key in BOOLS}}
    facts['account_known']=account
    if trusted_context is not None:
        if not isinstance(trusted_context,dict) or not set(trusted_context)<=TRUSTED_FIELDS:
            raise ValueError('trusted context outside allowlist')
        for key,value in trusted_context.items():
            if key in BOOLS or key=='intent_requested':
                if value is not None and type(value) is not bool:
                    raise ValueError('trusted boolean flag invalid')
            elif key=='site' and value not in (None,'tr'):
                raise ValueError('unsupported trusted site')
            elif key=='source_mode' and value not in (None,'MOCK','MARKET_ONLY','OKX_DEMO'):
                raise ValueError('unsupported trusted mode')
            elif key=='quantity' and value is not None:
                if type(value) not in (int,float,str) or len(str(value))>64:
                    raise ValueError('quantity must be sterile numeric scalar')
                try: Decimal(str(value))
                except InvalidOperation as exc: raise ValueError('quantity must be numeric') from exc
            facts[key]=value
        if 'account_known' in trusted_context and trusted_context['account_known'] is not None and account is not None and trusted_context['account_known']!=account:
            raise ValueError('conflicting trusted account facts')
    missing=[key for key,value in facts.items() if value is None]
    reasons=['missing_trusted_context:'+key for key in sorted(missing)]
    if not mapping_approved:
        reasons.insert(0,'trusted_context_mapping_not_approved')
    eligible=not reasons
    return {'facts':facts,'missing':sorted(missing),'eligible_for_shadow_inference':eligible,
        'reasons':reasons,'execution_authority':False,
        'normalized_state':json.dumps({'operational':facts},sort_keys=True,separators=(',',':')),
        'fallback':{'label':'REVIEW','confidence':0.0,'abstained':True,
            'model_version':'aegis-context-unavailable-v1','latency_ms':0.0} if not eligible else None}
