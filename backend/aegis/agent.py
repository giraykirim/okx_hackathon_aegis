import asyncio
import time
from datetime import timedelta
from decimal import Decimal

from .atk import ATK, ATKCommandError
from .cost_gate import CostConfig, EdgeEstimate, ExitPlan
from .cost_gate import evaluate as evaluate_cost
from .exit_plan import MAX_MARKET_AGE_SECONDS, ExitProposal, propose_exit_from_store
from .integrations import Models
from .laya_context import TrustedSignals, build_shadow_context
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
        # One trade per closed candle: the same signal must not trade again every cycle.
        self.last_traded_candle: str | None = None

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

    def emit_classify(self, laya: Classification, mode: str, context: dict | None = None) -> str:
        return self.emit(
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
                **(
                    {"context_version": context["context_version"], "missing": context["missing"]}
                    if context
                    else {}
                ),
            },
        )

    def operational_context(self, observation: Observation, proposal: Proposal, approval: bool) -> dict:
        """Trusted backend facts for LAYA; no balances, IDs, summaries or tool text enter the state."""
        entries = self.atk.journal.entries + self.models.journal.entries
        account_checked = self.atk.capabilities["ATK_ACCOUNT"].status == "PASS"
        precheck = check(
            observation,
            Classification(
                label="CONTINUE", confidence=1, abstained=False, model_version="precheck", latency_ms=0
            ),
            proposal,
            now=utcnow(),
            source_mode=self.settings.source_mode,
            approval_available=True,
            unresolved=False,
            duplicate=False,
            max_exposure_quote=self.settings.max_exposure_quote,
        )
        signals = TrustedSignals(
            approval_available=approval,
            api_timeout=any(not e["tool_call"]["success"] for e in entries) if entries else None,
            # Single proposing agent (EVREN): there is no competing typed proposal to disagree with.
            agents_disagree=False,
            # The account read verified read+trade without withdraw in this cycle.
            permission_revoked=False if account_checked else None,
            # EVREN output passed strict schema validation and tool calls are rejected upstream.
            injection_detected=False if self.models.capabilities["EVREN"].status == "PASS" else None,
            # LAYA responses are rejected on version mismatch when an expected version is pinned.
            deployment_integrity_failure=False if self.settings.laya_expected_version else None,
            excess_exposure="excess_exposure" in precheck.reasons,
        )
        return build_shadow_context(
            observation,
            proposal,
            settings=self.settings,
            now=utcnow(),
            signals=signals,
            duplicate=self.store.duplicate(proposal.intent_id),
            journal_statuses=[row["status"] for row in self.store.unresolved()],
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
                self._record_fill(row["intent_id"], decision.id, status)
            else:
                self.store.order_status(row["intent_id"], "UNKNOWN", venue_id, venue_state)
            self.emit(
                "VERIFY",
                "Prior order reconciled" if status != "UNKNOWN" else "Prior order remains UNKNOWN",
                actor="atk",
                severity="WARNING" if status == "UNKNOWN" else "INFO",
                details={"intent_id": row["intent_id"], "status": status, "venue_state": venue_state},
            )
        await self._backfill_fills()

    def _record_fill(self, intent_id: str, decision_id: str, status: str):
        """Persist venue-reported fill figures for PnL; never estimates a missing value."""
        fill = getattr(self.atk, "last_fill", None)
        if status not in {"VERIFIED", "PENDING"} or not fill:
            return
        if not fill.get("avg_price") or not fill.get("filled_qty"):
            return
        try:
            if Decimal(str(fill["filled_qty"])) <= 0:
                return
        except (ArithmeticError, ValueError):
            return
        self.store.record_fill(
            intent_id,
            {**fill, "intent_id": intent_id, "decision_id": decision_id, "recorded_at": utcnow().isoformat()},
        )

    async def _backfill_fills(self):
        """Read-only reconcile of every verified demo intent lacking a current-schema fill record.

        Driven by the intents journal (not a recent-decisions window), so no old order is missed;
        legacy records are refreshed once to capture venue fillTime and rebate fields.
        """
        if self.settings.source_mode != "OKX_DEMO":
            return
        current = self.store.fill_intents(schema=2)
        for row in self.store.verified_demo_intents():
            if row["intent_id"] in current or row["status"] != "VERIFIED":
                continue
            saved = self.store.db.execute(
                "SELECT body FROM decisions WHERE id=?", (row["client_id"],)
            ).fetchone()
            try:
                decision = Decision.model_validate_json(saved["body"]) if saved else None
                if decision is None or decision.limit_price is None:
                    continue
                proposal = Proposal.model_validate_json(row["proposal"])
                status, _, _ = await self.atk.reconcile(proposal, row["client_id"], decision.limit_price)
            except Exception:
                continue
            if status == "VERIFIED":
                self._record_fill(row["intent_id"], row["client_id"], status)

    def owned_sell_reasons(self, proposal: Proposal) -> list[str]:
        """A demo SELL may only spend the agent's own net inventory from the Store ledger.

        Account base_available may include foreign or preloaded BTC; unknown ownership fails closed.
        """
        try:
            quantity = Decimal(str(proposal.quantity))
            if not quantity.is_finite() or quantity <= 0:
                return []  # The policy gate already vetoes invalid quantities.
        except (ArithmeticError, ValueError, TypeError):
            return []
        try:
            pnl = self.store.demo_pnl()
            if not isinstance(pnl, dict):
                return ["owned_inventory_unavailable"]
            # PnL completeness also covers valuation: a missing mark alone withholds net PnL,
            # while Store still returns a trusted exact inventory. No accounting issue is allowed.
            issues = pnl.get("issues")
            accounting_known = (pnl.get("complete") is True and issues == []) or (
                pnl.get("complete") is False
                and pnl.get("valuation_status") == "NO_MARK"
                and issues == ["mark_price_missing"]
            )
            if not accounting_known:
                return ["owned_inventory_unavailable"]
            raw = pnl.get("inventory_qty")
            if not isinstance(raw, str):
                return ["owned_inventory_unavailable"]
            owned = Decimal(raw)
        except Exception:
            return ["owned_inventory_unavailable"]
        if not owned.is_finite() or owned < 0:
            return ["owned_inventory_unavailable"]
        return ["insufficient_owned_inventory"] if quantity > owned else []

    def trade_edge(self, features: dict | None) -> tuple[EdgeEstimate | None, ExitPlan | None]:
        """Measured expected edge and exit plan for a proposal.

        No validated return model or exit mechanism exists in this runtime: EVREN's direction
        and LAYA's confidence are not return forecasts, so nothing is returned and the cost gate
        routes every trade proposal to REVIEW instead of inventing an edge.
        """
        return None, None

    def market_liquidity(self) -> dict | None:
        return self.atk.last_top_of_book

    def record_exit_shadow(self, observation: Observation | None) -> None:
        """Persist a SHADOW exit assessment of the agent's verified owned inventory.

        Advisory only: it reuses ``propose_exit_from_store`` and never claims, places or
        reconciles, and it is independent of EVREN's action and of the entry cost gate.
        ``fraction=1`` is the full-close capacity after lot/minimum constraints, not a signal to
        sell now; no stop-loss, take-profit or time-based exit rule exists.
        """
        mode = self.settings.source_mode
        # A scripted MOCK market is not venue data and never supplies instrument constraints.
        market = None if mode == "MOCK" else observation
        try:
            computed_at = utcnow()
            basis = self.store.exit_inventory_basis()
            try:
                proposal = propose_exit_from_store(
                    self.store, fraction=Decimal(1), observation=market, now=computed_at
                )
            except Exception as exc:
                proposal = ExitProposal(
                    status="REVIEW",
                    reasons=["exit_assessment_failed", type(exc).__name__],
                    requested_fraction="1",
                    explanation="The shadow exit assessment could not be computed; no quantity proposed.",
                )
            self.store.record_exit_assessment(
                {
                    "schema_version": "aegis-exit-shadow-1",
                    "assessment_id": new_id(),
                    "run_id": self.run_id,
                    "cycle_id": self.cycle_id or new_id(),
                    "source_mode": mode,
                    "computed_at": computed_at.isoformat(),
                    "mode": "SHADOW",
                    "orders_sent": False,
                    "fraction_semantics": "full_close_capacity_not_a_sell_signal",
                    "market_source": "OKX ticker and instrument via official ATK"
                    if market is not None
                    else "MOCK_SCRIPTED_NOT_USED"
                    if mode == "MOCK"
                    else None,
                    # The read view re-judges market age against this bound; the record never refreshes it.
                    "market_max_age_seconds": MAX_MARKET_AGE_SECONDS,
                    "inventory_basis": basis,
                    "proposal": proposal.model_dump(mode="json"),
                }
            )
        except Exception as exc:
            # The shadow record must never change the cycle's decision path.
            self.emit(
                "ERROR",
                "Shadow exit assessment not persisted",
                severity="WARNING",
                details={"error_type": type(exc).__name__},
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
            features = None
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
                    self.record_exit_shadow(None)
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
            # After reconcile and this observation, before EVREN: model output cannot hide it.
            self.record_exit_shadow(observation)
            if mode != "MOCK":
                # LAYA judges operational context after the proposal (see post-proposal stage below).
                laya = Classification(
                    label="REVIEW",
                    confidence=0,
                    abstained=True,
                    model_version="pending-post-proposal",
                    latency_ms=0,
                )
            else:
                evidence.append(self.emit_classify(laya, mode))
            if mode != "MOCK":
                features = None
                try:
                    features = await self.atk.trend()
                    evidence.append(
                        self.emit(
                            "OBSERVE",
                            "Official ATK 15m candle trend features",
                            actor="atk",
                            details={"market_features": features},
                        )
                    )
                except Exception as exc:
                    evidence.append(
                        self.emit(
                            "OBSERVE",
                            "Trend features unavailable; EVREN told features are missing",
                            actor="atk",
                            severity="WARNING",
                            details={"error_type": type(exc).__name__},
                        )
                    )
                proposal = await self.models.reason(observation, laya, self.run_id, market_features=features)
                candle = features.get("candle_open_ts") if features else None
                if proposal.action != "NO_TRADE" and candle and candle == self.last_traded_candle:
                    proposal = proposal.model_copy(
                        update={
                            "action": "NO_TRADE",
                            "quantity": Decimal(0),
                            "summary": "Already traded on this closed 15m candle; waiting for the next one",
                        }
                    )
                # Intent identity is backend-owned; a model-chosen ID could collide across cycles.
                proposal = proposal.model_copy(update={"intent_id": new_id()})
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
            if mode != "MOCK" and proposal.action != "NO_TRADE":
                # Model latency can outlast the 15s freshness bound; gate on a fresh venue read.
                # A failed refresh keeps the old observation, so the stale-feed veto still applies.
                try:
                    observation = await self.atk.observe()
                    evidence.append(
                        self.emit(
                            "OBSERVE",
                            "Pre-gate ATK refresh after proposal",
                            actor="atk",
                            details=observation.model_dump(mode="json"),
                        )
                    )
                except Exception as exc:
                    evidence.append(
                        self.emit(
                            "OBSERVE",
                            "Pre-gate refresh failed; gating on original observation",
                            actor="atk",
                            severity="WARNING",
                            details={"error_type": type(exc).__name__},
                        )
                    )
            approval = (mode == "MOCK" and scenario != "missing_approval") or self.settings.demo_ready()
            approval = approval and not self.stop_requested
            if mode != "MOCK":
                context = self.operational_context(observation, proposal, approval)
                laya = await self.models.classify(
                    observation, self.run_id, self.cycle_id, context=context["state"]
                )
                evidence.append(self.emit_classify(laya, mode, context))
            for entry in self.atk.journal.entries + self.models.journal.entries:
                tool_id = entry["tool_call"]["evidence_id"]
                if tool_id not in evidence:
                    evidence.append(tool_id)
            self.last_observation, self.last_classification = observation, laya
            if mode != "MOCK":
                # Venue ticker with its exchange time; PnL valuation survives restarts.
                self.store.save_mark(observation)
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
                max_exposure_quote=self.settings.max_exposure_quote,
                laya_advisory=mode == "OKX_DEMO" and self.settings.laya_gate_demo == "advisory",
            )
            edge, exit_plan = self.trade_edge(features)
            cost = evaluate_cost(
                observation,
                proposal,
                now=utcnow(),
                config=CostConfig.from_settings(self.settings),
                edge=edge,
                exit_plan=exit_plan,
                top_of_book=self.market_liquidity() if mode != "MOCK" else None,
            )
            # Enforced wherever an exchange order could follow; MOCK/MARKET_ONLY record it advisory.
            cost_enforced = mode == "OKX_DEMO"
            if cost_enforced and cost.status != "NOT_APPLICABLE" and not cost.approved:
                gate = gate.model_copy(
                    update={
                        "approved": False,
                        "reasons": gate.reasons + [r for r in cost.reasons if r not in gate.reasons],
                    }
                )
            if mode == "OKX_DEMO" and proposal.action == "SELL":
                owned_reasons = self.owned_sell_reasons(proposal)
                if owned_reasons:
                    gate = gate.model_copy(
                        update={
                            "approved": False,
                            "reasons": gate.reasons + [r for r in owned_reasons if r not in gate.reasons],
                        }
                    )
            policy_latency_ms = (time.perf_counter() - policy_started) * 1000
            laya_avail = (
                "MOCK_SCRIPTED"
                if mode == "MOCK"
                else "UNAVAILABLE"
                if laya.model_version == "advisory-fallback"
                else "COMPLETED"
            )
            evren_avail = (
                "MOCK_SCRIPTED"
                if mode == "MOCK"
                else "COMPLETED"
                if self.models.capabilities["EVREN"].status == "PASS"
                else "UNAVAILABLE"
            )
            evren_model_name = (
                self.models.evren_metadata.get("model")
                if mode != "MOCK" and isinstance(self.models.evren_metadata, dict)
                else None
            )
            council = {
                "session_id": f"council-{(self.cycle_id or self.run_id)[:12]}",
                "state": "SKIPPED"
                if laya.label == "HALT"
                else "COMPLETED"
                if laya_avail == "COMPLETED" and evren_avail == "COMPLETED"
                else "DEGRADED"
                if "COMPLETED" in (laya_avail, evren_avail)
                else "COMPLETED"
                if mode == "MOCK"
                else "UNAVAILABLE",
                "headline": "MOCK COUNCIL DELIBERATION — Scripted Scenario"
                if mode == "MOCK"
                else "TradeCourt Multi-Seat Pre-Trade Deliberation",
                "summary": proposal.summary,
                "total_deliberation_ms": round(float(laya.latency_ms) + policy_latency_ms, 3)
                if mode != "MOCK"
                else None,
                "is_mock": mode == "MOCK",
                "seats": [
                    {
                        "seat_id": "REGIME_MAGISTRATE",
                        "role_title": "1. Regime Magistrate",
                        "subtitle": "LAYA Operational Regime Classifier",
                        "model_name": laya.model_version,
                        "actor": "mock" if mode == "MOCK" else "laya",
                        "status": laya_avail,
                        "stance": "VETO"
                        if laya.label == "HALT"
                        else "CAUTION"
                        if laya.label == "REVIEW" or laya.abstained
                        else "APPROVE",
                        "confidence": None if mode == "MOCK" or laya.abstained else float(laya.confidence),
                        "latency_ms": None if mode == "MOCK" or laya.latency_ms <= 0 else float(laya.latency_ms),
                        "rationale": f"LAYA classified operational context as {laya.label} (confidence={laya.confidence:.4f}).",
                        "flagged_rules": ["laya_not_clear"] if laya.label != "CONTINUE" or laya.abstained else [],
                        "is_mock": mode == "MOCK",
                    },
                    {
                        "seat_id": "OPPORTUNITY_ADVOCATE",
                        "role_title": "2. Opportunity Advocate",
                        "subtitle": "EVREN Bounded Thesis & Sizing Seat",
                        "model_name": evren_model_name,
                        "actor": "mock" if mode == "MOCK" else "evren",
                        "status": evren_avail,
                        "stance": "APPROVE"
                        if proposal.action in ("BUY", "SELL")
                        else "ABSTAIN"
                        if evren_avail == "UNAVAILABLE"
                        else "CAUTION",
                        "confidence": None,
                        "latency_ms": None,
                        "rationale": f"Proposed {proposal.action} ({proposal.quantity} {proposal.symbol}): {proposal.summary}",
                        "flagged_rules": ["no_trade_proposed"] if proposal.action == "NO_TRADE" else [],
                        "is_mock": mode == "MOCK",
                    },
                    {
                        "seat_id": "RISK_PROSECUTOR",
                        "role_title": "3. Risk Prosecutor",
                        "subtitle": "Adversarial Counter-Thesis & Safety Audit Seat",
                        "model_name": evren_model_name,
                        "actor": "mock" if mode == "MOCK" else "evren",
                        "status": evren_avail,
                        "stance": "VETO"
                        if not gate.approved and proposal.action != "NO_TRADE"
                        else "CAUTION"
                        if gate.reasons
                        else "APPROVE",
                        "confidence": None,
                        "latency_ms": None,
                        "rationale": (
                            f"Flagged safety conditions: {', '.join(gate.reasons)}"
                            if gate.reasons
                            else "All operational and exposure constraints satisfied."
                        ),
                        "flagged_rules": list(gate.reasons),
                        "is_mock": mode == "MOCK",
                    },
                    {
                        "seat_id": "PRESIDING_ARBITER",
                        "role_title": "4. Presiding Arbiter (Risk Gate)",
                        "subtitle": "Deterministic Python Execution Boundary",
                        "model_name": "policy-deterministic-v2",
                        "actor": "policy",
                        "status": "COMPLETED",
                        "stance": "APPROVE" if gate.approved else "VETO",
                        "confidence": None,
                        "latency_ms": round(policy_latency_ms, 3),
                        "rationale": (
                            "Deterministic Python Risk Gate approved bounded execution."
                            if gate.approved
                            else f"Deterministic Python Risk Gate enforced NO_TRADE ({', '.join(gate.reasons)})."
                        ),
                        "flagged_rules": list(gate.reasons),
                        "is_mock": False,
                    },
                ],
            }
            evidence.append(
                self.emit(
                    "RISK_GATE",
                    "Order approved" if gate.approved else "Order vetoed",
                    actor="policy",
                    severity="INFO" if gate.approved else "WARNING",
                    details={
                        **gate.model_dump(),
                        "policy_latency_ms": policy_latency_ms,
                        "run_budget": {
                            "orders_reserved": run_orders,
                            "notional_reserved": str(run_reserved),
                            "max_orders": self.settings.max_run_orders,
                            "max_notional": str(self.settings.max_run_notional),
                        },
                        "max_exposure_quote": str(self.settings.max_exposure_quote),
                        "laya_gate": self.settings.laya_gate_demo if mode == "OKX_DEMO" else "required",
                        "council": council,
                        "cost_assessment": cost.model_dump(mode="json"),
                        "cost_gate_enforced": cost_enforced,
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
            self.store.record_cost(
                decision.id,
                {
                    "decision_id": decision.id,
                    "run_id": self.run_id,
                    "source_mode": mode,
                    "timestamp": decision.timestamp.isoformat(),
                    "enforced": cost_enforced,
                    "assessment": cost.model_dump(mode="json"),
                },
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
                    venue_rejected = False
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
                        # An explicit venue error code means the venue answered; a timeout does not.
                        venue_rejected = isinstance(exc, ATKCommandError) and exc.code is not None
                        evidence.append(
                            self.emit(
                                "EXECUTE",
                                "Venue rejected submission; placement will not be retried"
                                if venue_rejected
                                else "Submission outcome ambiguous; placement will not be retried",
                                actor="atk",
                                severity="ERROR",
                                details={
                                    "error_type": type(exc).__name__,
                                    "error_code": getattr(exc, "code", None),
                                    "error_detail": getattr(exc, "detail", None),
                                },
                            )
                        )
                    try:
                        status, venue_id, state = await self.atk.reconcile(
                            proposal, decision.id, gate.limit_price
                        )
                        if status == "FAILED" and not venue_rejected:
                            # Not found right after an ambiguous submit is not proof; recheck next cycle.
                            status = "UNKNOWN"
                        decision.execution_status, decision.venue_order_id, decision.venue_state = (
                            status,
                            venue_id,
                            state,
                        )
                        self._record_fill(decision.intent_id, decision.id, status)
                        if status in {"VERIFIED", "PENDING"} and features:
                            self.last_traded_candle = features.get("candle_open_ts")
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
