"""Inactive post-proposal shadow mapping. Never called by public APIs or execution.

Only the orchestrator may construct TrustedSignals from independently checked facts.
Missing telemetry is None, never a healthy default. No free text or identifiers enter state.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, StrictBool

from .models import Observation, Proposal
from .settings import Settings

CONTEXT_VERSION = "aegis-trusted-context-shadow-v1"


class TrustedSignals(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    approval_available: StrictBool | None = None
    api_timeout: StrictBool | None = None
    agents_disagree: StrictBool | None = None
    permission_revoked: StrictBool | None = None
    injection_detected: StrictBool | None = None
    deployment_integrity_failure: StrictBool | None = None
    excess_exposure: StrictBool | None = None


def build_shadow_context(
    observation: Observation,
    proposal: Proposal | None,
    *,
    settings: Settings,
    now: datetime,
    signals: TrustedSignals | None = None,
    duplicate: bool | None = None,
    journal_statuses: list[str] | None = None,
) -> dict:
    observation = Observation.model_validate(observation.model_dump())
    if proposal is not None:
        proposal = Proposal.model_validate(proposal.model_dump())
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Aware backend clock required")
    if duplicate is not None and type(duplicate) is not bool:
        raise ValueError("Duplicate state must be a trusted boolean or unknown")
    if journal_statuses is not None and (
        not isinstance(journal_statuses, list)
        or any(s not in {"NOT_SENT", "PENDING", "UNKNOWN", "VERIFIED", "FAILED"} for s in journal_statuses)
    ):
        raise ValueError("Unrecognized journal state")
    facts = {
        "symbol": observation.symbol,
        "site": settings.okx_site,
        "source_mode": settings.source_mode,
        "feed_age_seconds": (now - observation.observed_at).total_seconds(),
        "intent_requested": None if proposal is None else proposal.action != "NO_TRADE",
        "quantity": None if proposal is None else str(proposal.quantity),
        # False is an explicit unknown-account flag, never an inferred available balance.
        "account_known": observation.account_known,
        **TrustedSignals.model_validate((signals or TrustedSignals()).model_dump()).model_dump(),
        "unknown_order": None if journal_statuses is None else "UNKNOWN" in journal_statuses,
        "duplicate_intent": duplicate,
    }
    missing = sorted(k for k, v in facts.items() if v is None)
    return {
        "state": {"operational": facts},
        "context_version": CONTEXT_VERSION,
        "missing": missing,
        "eligible_for_shadow_inference": not missing,
        "unresolved_order": None
        if journal_statuses is None
        else any(s in {"PENDING", "UNKNOWN"} for s in journal_statuses),
        "execution_authority": False,
        "runtime_enabled": False,
    }
