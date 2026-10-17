import asyncio
import time
from datetime import timedelta
from decimal import Decimal

from .atk import ATK
from .integrations import Models
from .models import (
    Capability,
    Classification,
    Decision,
    Event,
    Identity,
    Observation,
    Proposal,
    new_id,
    utcnow,
)
from .policy import check
from .settings import Settings
from .store import Store

SCENARIOS = {
    "normal",
    "stale_feed",
    "laya_halt",
    "excess_exposure",
    "invalid_quantity",
    "missing_approval",
    "unknown_order",
    "duplicate_intent",
}


class Agent:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.atk = ATK(settings)
        self.models = Models(settings)
        secrets = [
            v.get_secret_value()
            for name in (
                "control_token",
                "service_api_key",
                "okx_demo_api_key",
                "okx_demo_secret_key",
                "okx_demo_passphrase",
                "evren_api_key",
                "laya_token",
            )
            if (v := getattr(settings, name))
        ]
        self.store = Store(settings.db_path, secrets)
        # Persist each completed/failed attempt immediately, including cancellation and private calls.
        self.atk.evidence_sink = self.store.event
        self.models.evidence_sink = self.store.event
        self.lock = asyncio.Lock()
        self.wake = asyncio.Event()
        self.running = False
        self.stop_requested = False
        self.task: asyncio.Task | None = None
        self.run_id = new_id()
        self.last_observation: Observation | None = None
        self.last_classification: Classification | None = None
        self.last_cycle_at = None
        self.mock_execution_count = 0
        self.cycle_id: str | None = None

    def emit(self, event_type: str, message: str, *, actor="agent", severity="INFO", details=None) -> str:
        phases = {
            "OBSERVE": "OBSERVE",
            "CLASSIFY": "CLASSIFY",
            "REASON": "REASON",
            "RISK_GATE": "RISK_CHECK",
            "EXECUTE": "ACT",
            "NO_TRADE": "NO_TRADE",
            "VERIFY": "VERIFY",
            "AUDIT": "AUDIT",
        }
        details = dict(details or {})
        if event_type in phases:
            details.update(phase=phases[event_type], cycle_id=self.cycle_id, correlation_id=self.cycle_id)
        return self.store.event(
            Event(
                run_id=self.run_id,
                type=event_type,
                actor=actor,
                severity=severity,
                message=message,
                details=details,
                source_mode=self.settings.source_mode,
            )
        )

    def capabilities(self) -> dict:
        result = {**self.atk.capabilities, **self.models.capabilities, "ERC8004": Capability()}
        return self.store.sanitize({k: v.model_dump(mode="json") for k, v in result.items()})

    def snapshot(self) -> dict:
        return self.store.sanitize(
            {
                "running": self.running,
                "run_id": self.run_id,
                "source_mode": self.settings.source_mode,
                "last_cycle_at": self.last_cycle_at.isoformat() if self.last_cycle_at else None,
                "observation": self.last_observation.model_dump(mode="json")
                if self.last_observation
                else None,
                "classification": self.last_classification.model_dump(mode="json")
                if self.last_classification
                else None,
                "latest_decision": next(iter(self.store.decisions(1)), None),
                "capabilities": self.capabilities(),
                "identity": Identity().model_dump(mode="json"),
                "execution_enabled": self.settings.demo_ready(),
            }
        )

    async def start(self):
        if self.running:
            return
        self.running = True
        self.stop_requested = False
        self.run_id = new_id()
        self.wake.clear()
        self.task = asyncio.create_task(self.loop())
        self.emit("START", "Autonomous cycle started")

    async def stop(self):
        if self.stop_requested and not self.running and self.task is None:
            return
        self.running = False
        self.stop_requested = True
        self.wake.set()
        # Do not cancel an in-flight exchange operation. Wait for bounded I/O and journal reconciliation.
        if self.task:
            await self.task
            self.task = None
        self.emit("STOP", "Agent stopped; no new cycles will be started")

    async def close(self):
        if self.running or self.task:
            await self.stop()
        await self.models.close()
        self.store.close()

    async def loop(self):
        while self.running:
            try:
                await self.cycle()
            except Exception as exc:
                self.emit(
                    "ERROR",
                    "Cycle failed; execution remains blocked",
                    severity="ERROR",
                    details={"error_type": type(exc).__name__},
                )
                self.running = False
                break
            try:
                await asyncio.wait_for(self.wake.wait(), timeout=self.settings.cycle_seconds)
            except TimeoutError:
                pass

    async def reconcile_prior(self):
        if self.settings.source_mode != "OKX_DEMO":
            return
        for row in self.store.unresolved():
            if row["source_mode"] != "OKX_DEMO":
                continue
            saved = self.store.db.execute(
                "SELECT body FROM decisions WHERE id=?", (row["client_id"],)
            ).fetchone()
            decision = Decision.model_validate_json(saved["body"]) if saved else None
            try:
                if decision is None or decision.limit_price is None:
                    raise ValueError("Missing persisted policy decision")
                proposal = Proposal.model_validate_json(row["proposal"])
                status, venue_id, venue_state = await self.atk.reconcile(
                    proposal, row["client_id"], decision.limit_price
                )
            except Exception:
                status, venue_id, venue_state = "UNKNOWN", row["venue_order_id"], row["venue_state"]
            # Update the original decision so the dashboard reflects subsequent reconciliation.
            if decision:
                decision.execution_status, decision.venue_order_id, decision.venue_state = (
                    status,
                    venue_id,
                    venue_state,
                )
                self.store.finalize(decision)
            else:
                self.store.order_status(row["intent_id"], "UNKNOWN", venue_id, venue_state)
            self.emit(
                "VERIFY",
                "Prior order reconciled" if status != "UNKNOWN" else "Prior order remains UNKNOWN",
                actor="atk",
                severity="WARNING" if status == "UNKNOWN" else "INFO",
                details={"intent_id": row["intent_id"], "status": status, "venue_state": venue_state},
            )

    def mock_inputs(self, scenario: str):
        observation = Observation(
            symbol="BTC-USDT",
            observed_at=utcnow(),
            price="50000",
            ask="50001",
            bid="49999",
            min_size="0.00001",
            lot_size="0.00000001",
            instrument_live=True,
            account_known=True,
            quote_available="1000",
            base_available="0.01",
            exposure_quote="0",
        )
        laya = Classification(
            label="CONTINUE", confidence=1, abstained=False, model_version="MOCK-scripted", latency_ms=0
        )
        proposal = Proposal(
            action="BUY",
            symbol="BTC-USDT",
            quantity="0.0001",
            intent_id="mock-duplicate" if scenario == "duplicate_intent" else new_id(),
            summary="MOCK scripted proposal; no external model was called",
        )
        if scenario == "stale_feed":
            observation.observed_at -= timedelta(seconds=60)
        if scenario == "laya_halt":
            laya.label = "HALT"
        if scenario == "excess_exposure":
            observation.exposure_quote = Decimal("1001")
        if scenario == "invalid_quantity":
            proposal.quantity = Decimal("-1")
        if scenario == "no_trade":
            proposal.action = "NO_TRADE"
            proposal.quantity = Decimal(0)
        return observation, laya, proposal

    def audit_market_receipts(self):
        for receipt in self.atk.market_receipts:
            self.emit(
                "ATK_RECEIPT",
                "Official ATK market subprocess receipt",
                actor="atk",
                severity="INFO" if receipt.status == "PASS" else "ERROR",
                details=receipt.model_dump(mode="json"),
            )

    async def cycle(self, scenario: str | None = None) -> Decision:
        async with self.lock:
            self.cycle_id = new_id()
            try:
                return await self._cycle(scenario)
            except TimeoutError:
                self.running = False
                self.stop_requested = True
                self.wake.set()
                self.last_observation = None
                self.last_classification = None
                evidence = [
                    self.emit(
                        "ERROR",
                        "Cycle deadline exceeded; new execution blocked",
                        actor="policy",
                        severity="ERROR",
                        details={"reason": "cycle_timeout"},
                    )
                ]
                recovered = None
                for row in self.store.unresolved():
                    saved = self.store.db.execute(
                        "SELECT body FROM decisions WHERE id=?", (row["client_id"],)
                    ).fetchone()
                    if saved:
                        candidate = Decision.model_validate_json(saved["body"])
                        if candidate.run_id == self.run_id:
                            candidate.execution_status = "UNKNOWN"
                            candidate.risk_reasons = list(
                                dict.fromkeys(candidate.risk_reasons + ["cycle_timeout"])
                            )
                            candidate.evidence_ids.extend(evidence)
                            self.store.finalize(candidate)
                            recovered = candidate
                decision = recovered or Decision(
                    run_id=self.run_id,
                    symbol="BTC-USDT",
                    proposed_action="NO_TRADE",
                    laya_label="REVIEW",
                    laya_confidence=0,
                    llm_summary="Cycle deadline exceeded; NO_TRADE",
                    evidence_ids=evidence,
                    risk_approved=False,
                    risk_reasons=["cycle_timeout"],
                    execution_status="NOT_SENT",
                    source_mode=self.settings.source_mode,
                    intent_id=new_id(),
                    quantity="0",
                )
                self.store.finalize(decision)
                self.emit(
                    "AUDIT",
                    "Cycle timeout persisted; unresolved submissions remain blocked",
                    details={"decision_id": decision.id, "execution_status": decision.execution_status},
                )
                self.last_cycle_at = utcnow()
                return decision

    async def _cycle(self, scenario: str | None = None) -> Decision:
        if scenario and (self.settings.source_mode != "MOCK" or scenario not in SCENARIOS):
            raise ValueError("Scenarios are allowlisted and MOCK-only")
        async with asyncio.timeout(self.settings.cycle_timeout_seconds):
            self.models.begin_cycle(self.run_id, self.cycle_id)
            if self.settings.source_mode != "MOCK":
                self.atk.begin_observation(self.run_id, self.cycle_id)
            await self.reconcile_prior()
            evidence = []
            mode = self.settings.source_mode
            if mode == "MOCK":
                observation, laya, proposal = self.mock_inputs(
                    scenario or self.settings.mock_autonomous_scenario
                )
            else:
                try:
                    observation = await self.atk.observe()
                except Exception as exc:
                    self.audit_market_receipts()
                    self.atk.capabilities["ATK_MARKET"] = Capability(
                        status="FAIL",
                        checked_at=utcnow(),
                        evidence=["ATK market observation failed: " + type(exc).__name__],
                    )
                    self.last_observation = None
                    self.last_classification = None
                    evidence.append(
                        self.emit(
                            "OBSERVE",
                            "Market observation unavailable",
                            actor="atk",
                            severity="ERROR",
                            details={"error_type": type(exc).__name__},
                        )
                    )
                    decision = Decision(
                        run_id=self.run_id,
                        symbol="BTC-USDT",
                        proposed_action="NO_TRADE",
                        laya_label="REVIEW",
                        laya_confidence=0,
                        llm_summary="Observation unavailable; NO_TRADE",
                        evidence_ids=evidence,
                        risk_approved=False,
                        risk_reasons=["observation_unavailable"],
                        execution_status="NOT_SENT",
                        source_mode=mode,
                        intent_id=new_id(),
                        quantity="0",
                    )
                    self.store.decision(decision)
                    self.emit(
                        "AUDIT",
                        "Failed observation audited as NO_TRADE",
                        details={"decision_id": decision.id},
                    )
                    self.last_cycle_at = utcnow()
                    return decision
                self.audit_market_receipts()
            evidence.append(
                self.emit(
                    "OBSERVE",
                    "Scripted MOCK observation" if mode == "MOCK" else "Official ATK market observation",
                    actor="mock" if mode == "MOCK" else "atk",
                    details=observation.model_dump(mode="json"),
                )
            )
            if mode != "MOCK":
                laya = await self.models.classify(observation, self.run_id, self.cycle_id)
            evidence.append(
                self.emit(
                    "CLASSIFY",
                    "Operational risk classified",
                    actor="mock" if mode == "MOCK" else "laya",
                    details={
                        **laya.model_dump(mode="json"),
                        "integration": self.models.laya_metadata
                        if mode != "MOCK"
                        else {
                            "availability": "SCRIPTED",
                            "source": "INJECTED_MOCK",
                            "model_version": laya.model_version,
                        },
                        "availability": "SCRIPTED"
                        if mode == "MOCK"
                        else "UNAVAILABLE"
                        if laya.model_version == "advisory-fallback"
                        else "AVAILABLE",
                    },
                )
            )
            if mode != "MOCK":
                proposal = await self.models.reason(observation, laya, self.run_id)
            evidence.append(
                self.emit(
                    "REASON",
                    "Typed proposal received",
                    actor="mock" if mode == "MOCK" else "evren",
                    details={
                        **proposal.model_dump(mode="json"),
                        "integration": self.models.evren_metadata
                        if mode != "MOCK"
                        else {
                            "availability": "SCRIPTED",
                            "source": "INJECTED_MOCK",
                            "model": None,
                        },
                        "availability": "SCRIPTED"
                        if mode == "MOCK"
                        else "AVAILABLE"
                        if self.models.capabilities["EVREN"].status == "PASS"
                        else "FALLBACK",
                    },
                )
            )
            for entry in self.atk.journal.entries + self.models.journal.entries:
                tool_id = entry["tool_call"]["evidence_id"]
                if tool_id not in evidence:
                    evidence.append(tool_id)
            self.last_observation, self.last_classification = observation, laya
            approval = (mode == "MOCK" and scenario != "missing_approval") or self.settings.demo_ready()
            approval = approval and not self.stop_requested
            run_orders, run_reserved = self.store.run_budget(self.run_id)
            policy_started = time.perf_counter()
            gate = check(
                observation,
                laya,
                proposal,
                now=utcnow(),
                source_mode=mode,
                approval_available=approval,
                unresolved=bool(self.store.unresolved()) or scenario == "unknown_order",
                duplicate=self.store.duplicate(proposal.intent_id),
                run_order_count=run_orders,
                run_reserved_notional=run_reserved,
                max_run_orders=self.settings.max_run_orders,
                max_run_notional=self.settings.max_run_notional,
            )
            evidence.append(
                self.emit(
                    "RISK_GATE",
                    "Order approved" if gate.approved else "Order vetoed",
                    actor="policy",
                    severity="INFO" if gate.approved else "WARNING",
                    details={
                        **gate.model_dump(),
                        "policy_latency_ms": (time.perf_counter() - policy_started) * 1000,
                        "run_budget": {
                            "orders_reserved": run_orders,
                            "notional_reserved": str(run_reserved),
                            "max_orders": self.settings.max_run_orders,
                            "max_notional": str(self.settings.max_run_notional),
                        },
                    },
                )
            )
            decision = Decision(
                run_id=self.run_id,
                symbol=proposal.symbol,
                proposed_action=proposal.action,
                laya_label=laya.label,
                laya_confidence=laya.confidence,
                llm_summary=proposal.summary,
                evidence_ids=evidence,
                risk_approved=gate.approved,
                risk_reasons=gate.reasons,
                execution_status="NOT_SENT",
                source_mode=mode,
                intent_id=proposal.intent_id,
                quantity=proposal.quantity,
                limit_price=gate.limit_price,
            )
            if gate.approved:
                if mode == "OKX_DEMO":
                    decision.execution_status = "PENDING"
                reserved_notional = (
                    proposal.quantity
                    * max(gate.limit_price, observation.ask, observation.price)
                    * Decimal("1.01")
                )
                if not self.store.claim(
                    proposal,
                    decision.id,
                    mode,
                    pending_decision=decision,
                    run_id=self.run_id,
                    reserved_notional=reserved_notional,
                    max_run_orders=self.settings.max_run_orders,
                    max_run_notional=self.settings.max_run_notional,
                ):
                    decision.risk_approved = False
                    decision.execution_status = "NOT_SENT"
                    decision.risk_reasons.append("atomic_claim_denied")
                elif mode == "MOCK":
                    self.mock_execution_count += 1
                    decision.venue_state = "MOCK_FILLED"
                    evidence.append(
                        self.emit(
                            "EXECUTE",
                            "MOCK executor simulated a fill; no exchange order sent",
                            actor="mock",
                            details={"decision_id": decision.id},
                        )
                    )
                    evidence.append(
                        self.emit("VERIFY", "MOCK simulation only; exchange status NOT_SENT", actor="mock")
                    )
                else:
                    try:
                        decision.venue_order_id = await self.atk.place(
                            proposal, decision.id, gate.limit_price
                        )
                        evidence.append(
                            self.emit(
                                "EXECUTE",
                                "Demo submission acknowledged; reconciliation required",
                                actor="atk",
                                details={"venue_order_id": decision.venue_order_id},
                            )
                        )
                    except Exception as exc:
                        evidence.append(
                            self.emit(
                                "EXECUTE",
                                "Submission outcome ambiguous; placement will not be retried",
                                actor="atk",
                                severity="ERROR",
                                details={"error_type": type(exc).__name__},
                            )
                        )
                    try:
                        status, venue_id, state = await self.atk.reconcile(
                            proposal, decision.id, gate.limit_price
                        )
                        decision.execution_status, decision.venue_order_id, decision.venue_state = (
                            status,
                            venue_id,
                            state,
                        )
                    except Exception:
                        decision.execution_status = "UNKNOWN"
                    evidence.append(
                        self.emit(
                            "VERIFY",
                            "Venue reconciliation completed",
                            actor="atk",
                            severity="WARNING" if decision.execution_status == "UNKNOWN" else "INFO",
                            details={
                                "execution_status": decision.execution_status,
                                "venue_state": decision.venue_state,
                            },
                        )
                    )
            else:
                evidence.append(
                    self.emit("NO_TRADE", "No order sent", actor="policy", details={"reasons": gate.reasons})
                )
                evidence.append(
                    self.emit(
                        "VERIFY",
                        "NOT_SENT: policy path made no submission call",
                        actor="policy",
                        details={"execution_status": "NOT_SENT", "venue_reconciliation": "NOT_REQUIRED"},
                    )
                )
            decision.evidence_ids = evidence
            self.store.finalize(decision)
            self.emit(
                "AUDIT",
                "Cycle persisted",
                details={
                    "decision_id": decision.id,
                    "execution_status": decision.execution_status,
                    "intent_id": decision.intent_id,
                    "verdict": "ALLOW_DEMO_ONLY"
                    if decision.risk_approved
                    else "HALT"
                    if proposal.action != "NO_TRADE"
                    else "NO_TRADE",
                    "risk_reasons": decision.risk_reasons,
                    "input_source": mode,
                },
            )
            self.last_cycle_at = utcnow()
            return decision
