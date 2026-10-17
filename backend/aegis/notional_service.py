import asyncio
import hashlib
import json
import time
from decimal import ROUND_FLOOR, Decimal

from fastapi import HTTPException

from .models import Classification, Event, Observation, Proposal, utcnow
from .policy import check
from .service_models import RiskEvaluationRequest, RiskEvaluationResponse
from .store import RequestConflictError

POLICY_VERSION = "risk-service-1.1.0"
IMPLEMENTATION_REVISION = "shared-deterministic-gate-2026-10-17"


class NotionalService:
    def __init__(self, parent):
        self.parent = parent

    async def evaluate(self, request: RiskEvaluationRequest) -> RiskEvaluationResponse:
        service = self.parent
        mode = service.settings.service_source_mode
        key = service.settings.service_api_key
        namespace = hashlib.sha256(
            json.dumps(
                [POLICY_VERSION, IMPLEMENTATION_REVISION, mode, key.get_secret_value() if key else "disabled"]
            ).encode()
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
        policy_result, policy_latency_ms = None, None
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
                observation = Observation.model_validate(observation.model_dump())
                # The public service never borrows an operator account or invents balances.
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
                # Derive an assessment-only, lot-aligned quantity from public prices.
                # This is neither a venue order nor an executable sizing recommendation.
                units = (
                    Decimal(request.proposed_notional)
                    / (max(observation.ask, observation.price) * observation.lot_size)
                ).to_integral_value(rounding=ROUND_FLOOR)
                proposal = Proposal(
                    action=request.proposed_action,
                    symbol=request.symbol,
                    quantity=units * observation.lot_size,
                    intent_id=request.request_id,
                    summary="Public notional assessment only; no execution authority",
                )
                started = time.perf_counter()
                gate = check(
                    observation,
                    Classification(
                        label="REVIEW",
                        confidence=0,
                        abstained=True,
                        model_version="deterministic-assessment-only",
                        latency_ms=0,
                    ),
                    proposal,
                    now=utcnow(),
                    source_mode="MARKET_ONLY",
                    approval_available=False,
                    unresolved=False,
                    duplicate=False,
                )
                policy_latency_ms = (time.perf_counter() - started) * 1000
                policy_result = gate.model_dump(mode="json")
                # Unknown account placeholders cannot justify balance/exposure findings.
                account_findings = {
                    "insufficient_quote",
                    "insufficient_base",
                    "excess_exposure",
                    "stale_account",
                    "unknown_account_timestamp",
                }
                findings = [r for r in gate.reasons if r not in account_findings]
                reasons.extend(r.upper() for r in findings)
                reasons.extend(["DETERMINISTIC_POLICY_EVALUATED", "MODEL_ANALYSIS_NOT_REQUESTED"])
                hard = {
                    "stale_feed",
                    "future_feed",
                    "instrument_unavailable",
                    "invalid_quantity",
                    "excess_order_notional",
                    "symbol_not_allowed",
                    "crossed_quotes",
                    "invalid_execution_price",
                    "corrupt_data",
                }
                blocked = blocked or bool(hard.intersection(findings))
            except TimeoutError:
                reasons.append("ASSESSMENT_TIMEOUT")
            except (ValueError, ArithmeticError):
                blocked = True
                reasons.append("CORRUPT_MARKET_DATA")
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
                "policy_implementation_revision": IMPLEMENTATION_REVISION,
                "deterministic_policy": policy_result,
                "policy_latency_ms": policy_latency_ms,
                "quantity_source": "SERVER_DERIVED_FROM_PUBLIC_MARKET_NOT_EXECUTABLE"
                if policy_result
                else None,
            },
        )
        result = RiskEvaluationResponse(
            request_id=request.request_id,
            verdict="BLOCK" if blocked else "UNAVAILABLE",
            reason_codes=list(dict.fromkeys(reasons)),
            evidence_ids=[e.id for e in events] + [audit.id],
            evaluated_at=evaluated_at,
            source_mode=mode,
        )
        audit.details["response"] = result.model_dump(mode="json")
        events.append(audit)
        body = service.store.save_evaluation(namespace, fingerprint, result.model_dump(mode="json"), events)
        return RiskEvaluationResponse.model_validate(body)
