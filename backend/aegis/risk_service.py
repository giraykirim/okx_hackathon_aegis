import asyncio
import hashlib
import json
import math
import time
from collections import deque
from decimal import Decimal

from fastapi import HTTPException

from .atk import ATK
from .integrations import Models
from .models import Capability, Classification, Event, Proposal, new_id, utcnow
from .notional_service import NotionalService
from .policy import check
from .service_models import (
    MarketChecks,
    MarketProvenance,
    RiskAssessment,
    RiskRequest,
    ServiceAuth,
    ServiceInfo,
)
from .settings import Settings
from .store import Store

HARD_MARKET_REASONS = {
    "stale_feed",
    "future_feed",
    "instrument_unavailable",
    "invalid_quantity",
    "excess_order_notional",
    "symbol_not_allowed",
    "crossed_quotes",
    "invalid_execution_price",
}
LIMITATIONS = [
    "Pre-trade operational assessment only; never an execution approval or financial advice",
    "External account balances, exposure and prior orders are unavailable and are not inferred",
    "Caller intent is untrusted input; market and instrument facts come from server-side official ATK",
    "An assessment is a timestamped observation, not a guarantee of later venue conditions",
]


class RiskService:
    def __init__(self, settings: Settings, store: Store, *, evren_budget=None):
        self.settings = settings
        self.store = store
        # A separate observer cannot borrow the operator's account, even when the demo loop is enabled.
        public_settings = settings.model_copy(
            update={
                "source_mode": "MARKET_ONLY",
                # Preserve the frozen service's CLI-only ATKReceipt identity and payload.
                "atk_transport": "cli",
                "demo_enabled": False,
                "demo_region_confirmed": False,
                "okx_demo_api_key": None,
                "okx_demo_secret_key": None,
                "okx_demo_passphrase": None,
                # Keep the public assessment inside its own deadline even if the operator raises EVREN's.
                "evren_timeout_seconds": min(settings.evren_timeout_seconds, 15),
                "max_exposure_quote": Decimal("1000"),
            }
        )
        self.atk = ATK(public_settings)
        self.models = Models(public_settings, budget=evren_budget)
        self.hits: deque[float] = deque()
        self.lock = asyncio.Lock()
        self.notional = NotionalService(self)

    async def close(self):
        await self.models.close()

    def info(self) -> ServiceInfo:
        key = self.settings.service_api_key
        return ServiceInfo(
            notional_source_mode=self.settings.service_source_mode,
            auth=ServiceAuth(
                configured=bool(key and key.get_secret_value()),
                requests_per_minute=self.settings.service_requests_per_minute,
            ),
            limitations=LIMITATIONS,
        )

    def admit(self):
        now = time.monotonic()
        while self.hits and now - self.hits[0] >= 60:
            self.hits.popleft()
        if len(self.hits) >= self.settings.service_requests_per_minute:
            retry = max(1, math.ceil(60 - (now - self.hits[0])))
            raise HTTPException(429, "Assessment rate limit reached", headers={"Retry-After": str(retry)})
        if self.lock.locked():
            raise HTTPException(429, "Another assessment is in progress", headers={"Retry-After": "1"})
        self.hits.append(now)

    async def evaluate(self, request: RiskRequest) -> RiskAssessment:
        self.admit()
        async with self.lock:
            assessment_id = new_id()
            timestamp = utcnow()
            self.models.capabilities = {name: Capability() for name in self.models.capabilities}
            self.models.begin_cycle(assessment_id, assessment_id)
            self.models.selected_model = None
            self.atk.begin_observation(assessment_id)
            observation = None
            laya = Classification(
                label="REVIEW", confidence=0, abstained=True, model_version="advisory-fallback", latency_ms=0
            )
            analysis = "EVREN unavailable; operational assessment uses deterministic checks only"
            reasons = []
            limit_price = None
            try:
                async with asyncio.timeout(self.settings.service_timeout_seconds):
                    observation = await self.atk.observe()
                    # Ignore any account data accidentally returned by a future market adapter.
                    observation = observation.model_copy(
                        update={
                            "account_known": False,
                            "exposure_quote": Decimal(0),
                            "quote_available": Decimal(0),
                            "base_available": Decimal(0),
                            "account_observed_at": None,
                            "external_open_orders": False,
                        }
                    )
                    laya = await self.models.classify(observation, assessment_id, assessment_id)
                    bounded = await self.models.reason(
                        observation, laya, assessment_id, assessment=request.model_dump(mode="json")
                    )
                    analysis = bounded.summary
            except TimeoutError:
                reasons.append("assessment_timeout")
            except Exception:
                reasons.append(
                    "market_observation_unavailable" if observation is None else "assessment_unavailable"
                )
            if observation is not None:
                # Revalidate through the original deterministic gate; no order permission can be produced.
                proposal = Proposal(
                    action=request.action,
                    symbol=request.symbol,
                    quantity=request.quantity,
                    intent_id=assessment_id,
                    summary="External intent; assessment only",
                )
                gate = check(
                    observation,
                    laya,
                    proposal,
                    now=utcnow(),
                    source_mode="MARKET_ONLY",
                    approval_available=False,
                    unresolved=False,
                    duplicate=False,
                )
                # Zero placeholders are not verified account balances or exposure findings.
                account_findings = {
                    "insufficient_quote",
                    "insufficient_base",
                    "excess_exposure",
                    "stale_account",
                    "unknown_account_timestamp",
                }
                reasons.extend(r for r in gate.reasons if r not in account_findings)
                limit_price = gate.limit_price
            else:
                reasons.extend(["unknown_account", "execution_disabled", "approval_unavailable"])
            hard = [r for r in reasons if r in HARD_MARKET_REASONS]
            failed = any(
                r in reasons
                for r in ("assessment_timeout", "assessment_unavailable", "market_observation_unavailable")
            )
            receipts = list(self.atk.market_receipts)
            evidence_ids = [
                self.store.event(event) for event in self.atk.tool_events() + self.models.tool_events()
            ]
            for receipt in receipts:
                evidence_ids.append(
                    self.store.event(
                        Event(
                            run_id=assessment_id,
                            type="ATK_RECEIPT",
                            severity="INFO" if receipt.status == "PASS" else "ERROR",
                            actor="atk",
                            message="Official ATK market subprocess receipt",
                            source_mode="MARKET_ONLY",
                            details=receipt.model_dump(mode="json"),
                        )
                    )
                )
            result = RiskAssessment(
                assessment_id=assessment_id,
                timestamp=timestamp,
                run_id=assessment_id,
                request=request,
                assessment="HALT" if hard or failed or laya.label == "HALT" else "REVIEW",
                reasons=list(dict.fromkeys(reasons)),
                market_provenance=MarketProvenance(
                    status="PASS" if observation is not None else "UNAVAILABLE",
                    site=self.settings.okx_site,
                    market_timestamp=observation.observed_at if observation else None,
                    receipts=receipts,
                ),
                market_checks=MarketChecks(
                    status="FAIL" if hard else "PASS" if observation is not None else "UNAVAILABLE",
                    reasons=hard,
                    policy_limit_price=limit_price,
                ),
                classification=laya,
                laya_status="AVAILABLE" if laya.model_version != "advisory-fallback" else "UNAVAILABLE",
                evren_status="AVAILABLE"
                if self.models.capabilities["EVREN"].status == "PASS"
                else "FALLBACK",
                analysis_summary=analysis,
                limitations=LIMITATIONS,
                evidence_ids=evidence_ids,
                assessment_sha256="",
            )
            body = self.store.sanitize(result.model_dump(mode="json"))
            body.pop("assessment_sha256")
            body["assessment_sha256"] = hashlib.sha256(
                json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            result = RiskAssessment.model_validate(body)
            # Separate event namespace: a service assessment is never an executed trading Decision.
            self.store.event(
                Event(
                    run_id=assessment_id,
                    type="SERVICE_ASSESSMENT",
                    severity="WARNING",
                    actor="risk-service",
                    message="Assessment recorded; no order permission or execution authority",
                    source_mode="MARKET_ONLY",
                    details=result.model_dump(mode="json"),
                )
            )
            return result
