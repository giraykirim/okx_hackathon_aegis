import asyncio
import hashlib
import json
from decimal import Decimal

from fastapi import HTTPException

from .models import Event, utcnow
from .service_models import RiskEvaluationRequest, RiskEvaluationResponse
from .store import RequestConflictError

POLICY_VERSION = "risk-service-1.1.0"


class NotionalService:
    def __init__(self, parent):
        self.parent = parent

    async def evaluate(self, request: RiskEvaluationRequest) -> RiskEvaluationResponse:
        service = self.parent
        mode = service.settings.service_source_mode
        key = service.settings.service_api_key
        namespace = hashlib.sha256(
            json.dumps([POLICY_VERSION, mode, key.get_secret_value() if key else "disabled"]).encode()
        ).hexdigest()
        intent = {
            "symbol": request.symbol,
            "proposed_action": request.proposed_action,
            "proposed_notional": format(Decimal(request.proposed_notional).normalize(), "f"),
        }
        fingerprint = hashlib.sha256(json.dumps(intent, sort_keys=True).encode()).hexdigest()
        try:
            cached = service.store.evaluation(namespace, request.request_id, fingerprint)
            if cached is not None:
                return RiskEvaluationResponse.model_validate(cached)
            service.admit()
            async with service.lock:
                return await self.assess(request, mode, namespace, fingerprint, intent)
        except RequestConflictError:
            raise HTTPException(409, "Request ID already belongs to a different effective intent") from None

    async def assess(self, request, mode, namespace, fingerprint, intent):
        service = self.parent
        evaluated_at = utcnow()
        reasons = ["ACCOUNT_DATA_UNAVAILABLE", "EXECUTION_NOT_AUTHORIZED"]
        blocked = Decimal(request.proposed_notional) > 25
        if blocked:
            reasons.append("EXCESS_ORDER_NOTIONAL")
        if request.proposed_action == "NO_TRADE":
            reasons.append("NO_TRADE_REQUESTED")
            blocked = True
        receipts = []
        if mode == "MOCK":
            reasons.extend(
                ["MOCK_DATA_ONLY", "REAL_MARKET_DATA_UNAVAILABLE", "LAYA_UNAVAILABLE", "EVREN_FALLBACK"]
            )
        else:
            service.atk.begin_observation(request.request_id)
            try:
                async with asyncio.timeout(service.settings.service_timeout_seconds):
                    observation = await service.atk.observe()
                reasons.append("SERVER_MARKET_OBSERVED")
                age = (utcnow() - observation.observed_at).total_seconds()
                for failed, code in (
                    (age > 15, "STALE_FEED"),
                    (age < -2, "FUTURE_FEED"),
                    (not observation.instrument_live, "INSTRUMENT_UNAVAILABLE"),
                    (observation.bid > observation.ask, "CROSSED_QUOTES"),
                ):
                    if failed:
                        blocked = True
                        reasons.append(code)
            except TimeoutError:
                reasons.append("ASSESSMENT_TIMEOUT")
            except Exception:
                reasons.append("MARKET_DATA_UNAVAILABLE")
            receipts = service.atk.market_receipts
        events = [
            Event(
                run_id=request.request_id,
                type="ATK_RECEIPT",
                severity="INFO" if r.status == "PASS" else "ERROR",
                actor="atk",
                source_mode=mode,
                message="Official ATK market subprocess receipt",
                details=r.model_dump(mode="json"),
            )
            for r in receipts
        ]
        if mode != "MOCK":
            events = service.atk.tool_events() + events
        audit = Event(
            run_id=request.request_id,
            type="SERVICE_ASSESSMENT",
            severity="WARNING",
            actor="risk-service",
            source_mode=mode,
            message="Notional assessment; no execution authorization",
            details={
                "phase": "AUDIT",
                "request_id": request.request_id,
                "effective_intent": intent,
                "requester_context_used": False,
                "policy_version": POLICY_VERSION,
            },
        )
        result = RiskEvaluationResponse(
            request_id=request.request_id,
            verdict="BLOCK" if blocked else "UNAVAILABLE",
            reason_codes=reasons,
            evidence_ids=[e.id for e in events] + [audit.id],
            evaluated_at=evaluated_at,
            source_mode=mode,
        )
        audit.details["response"] = result.model_dump(mode="json")
        events.append(audit)
        body = service.store.save_evaluation(namespace, fingerprint, result.model_dump(mode="json"), events)
        return RiskEvaluationResponse.model_validate(body)
