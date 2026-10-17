"""Pinned pure backend replay. No settings, executor, ATK, auth, HTTP or account IO."""

import hashlib
import importlib.util
import socket
import subprocess
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]
GIT = Path("C:/Users/hackathon/AppData/Local/HackathonTools/git/cmd/git.exe")
MODULES = ("models", "policy", "store")
NOW = datetime(2026, 10, 17, 12, tzinfo=UTC)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def block_network():
    def denied(*args, **kwargs):
        raise RuntimeError("Network forbidden in offline data expansion")

    socket.socket.connect = denied
    socket.socket.connect_ex = denied
    socket.create_connection = denied
    socket.getaddrinfo = denied


def git(*args):
    return subprocess.run(
        [str(GIT), *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        timeout=30,
    ).stdout


def snapshot_backend(output):
    """Only committed dependency-free modules; reject overlapping local changes."""
    commit = git("rev-parse", "HEAD").decode().strip()
    target = output / "backend_snapshot"
    target.mkdir(exist_ok=False)
    hashes = {}
    for name in MODULES:
        relative = f"backend/aegis/{name}.py"
        committed = git("show", f"{commit}:{relative}")
        current = (ROOT / relative).read_bytes()
        if current.replace(b"\r\n", b"\n") != committed.replace(b"\r\n", b"\n"):
            raise ValueError("backend module locally changed; coordinate before replay")
        (target / f"{name}.py").write_bytes(committed)
        hashes[name + ".py"] = digest(target / f"{name}.py")
    return commit, target, hashes


def load_backend(snapshot):
    package_name = "_aegis_dataset_offline"
    package = ModuleType(package_name)
    package.__path__ = [str(snapshot)]
    sys.modules[package_name] = package
    loaded = {}
    for name in MODULES:
        module_name = package_name + "." + name
        spec = importlib.util.spec_from_file_location(
            module_name, snapshot / f"{name}.py"
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        loaded[name] = module
    return loaded


def observation(models, age=2, **updates):
    values = {
        "symbol": "BTC-USDT",
        "observed_at": NOW - timedelta(seconds=age),
        "price": "50000",
        "bid": "49999",
        "ask": "50001",
        "min_size": "0.00001",
        "lot_size": "0.00000001",
        "tick_size": "0.1",
        "instrument_live": True,
        "account_known": True,
        "quote_available": "1000",
        "base_available": "0.1",
        "exposure_quote": "0",
    }
    values.update(updates)
    return models.Observation(**values)


def stub(models):
    return models.Classification(
        label="CONTINUE",
        confidence=1,
        abstained=False,
        model_version="OFFLINE_TEST_STUB_NOT_LAYA",
        latency_ms=0,
    )


def lifecycle_replay(modules, quantity, scenario):
    """Store calls are real; delivery/venue events are injected fixtures, NOT receipts.

    A PENDING record is not automatically an unknown submission. Caller must retain
    the distinction between unknown outcome and a known active order.
    """
    models, policy, store_module = (modules[n] for n in MODULES)
    work = ROOT.parent / "work"
    if not work.is_dir():
        raise ValueError("existing task work directory required")
    events = []
    with tempfile.TemporaryDirectory(
        prefix="aegis-data-offline-", dir=work
    ) as temporary:
        temp_path = Path(temporary).resolve()
        if not temp_path.is_relative_to(work.resolve()):
            raise ValueError("temporary journal outside task workspace")
        store = store_module.Store(temp_path / "fixture.sqlite", secrets=[])
        proposal = models.Proposal(
            action="BUY",
            symbol="BTC-USDT",
            quantity=quantity,
            intent_id="fixture-original",
            summary="Synthetic offline journal exercise",
        )
        new_proposal = models.Proposal(
            action="BUY",
            symbol="BTC-USDT",
            quantity=quantity,
            intent_id="fixture-new",
            summary="Synthetic offline journal exercise",
        )
        unknown_order = False
        intent_requested = True
        duplicate = False
        api_timeout = False
        try:
            if scenario == "read_timeout_before_submit":
                api_timeout = True
                events.append(
                    {
                        "step": "read",
                        "fixture_outcome": "timeout_before_submit",
                        "journal_claim_called": False,
                    }
                )
            else:
                claimed = store.claim(proposal, "fixture-client", "MOCK")
                if not claimed:
                    raise ValueError(
                        "fresh temporary journal claim unexpectedly failed"
                    )
                events.append(
                    {
                        "step": "claim",
                        "backend_method": "Store.claim",
                        "accepted": claimed,
                        "unresolved_count": len(store.unresolved()),
                    }
                )
                if scenario == "submit_timeout_unknown":
                    store.order_status(proposal.intent_id, "UNKNOWN")
                    unknown_order = any(
                        row["status"] == "UNKNOWN" for row in store.unresolved()
                    )
                    events.append(
                        {
                            "step": "injected_transport_timeout",
                            "backend_method": "Store.order_status",
                            "stored_status": "UNKNOWN",
                            "delivery": "unknown",
                        }
                    )
                elif scenario in (
                    "place_ack_only",
                    "cancel_ack_only",
                    "new_intent_while_pending",
                ):
                    state = (
                        "cancel_requested" if scenario == "cancel_ack_only" else None
                    )
                    store.order_status(proposal.intent_id, "PENDING", venue_state=state)
                    unknown_order = None
                    events.append(
                        {
                            "step": "injected_ack_only",
                            "backend_method": "Store.order_status",
                            "stored_status": "PENDING",
                            "terminal_receipt_available": False,
                        }
                    )
                    if scenario == "new_intent_while_pending":
                        accepted = store.claim(
                            new_proposal, "fixture-new-client", "MOCK"
                        )
                        if accepted:
                            raise ValueError(
                                "second unresolved claim should be rejected"
                            )
                        events.append(
                            {
                                "step": "second_intent",
                                "backend_method": "Store.claim",
                                "accepted": accepted,
                            }
                        )
                elif scenario in ("active_partial", "active_live"):
                    state = (
                        "partially_filled" if scenario == "active_partial" else "live"
                    )
                    store.order_status(proposal.intent_id, "PENDING", venue_state=state)
                    intent_requested = False
                    events.append(
                        {
                            "step": "injected_known_active_query",
                            "backend_method": "Store.order_status",
                            "stored_status": "PENDING",
                            "fixture_venue_state": state,
                            "fixture_order_type": "ioc"
                            if scenario == "active_partial"
                            else "limit",
                            "fixture_fill_size": str(Decimal(quantity) / 2)
                            if scenario == "active_partial"
                            else "0",
                        }
                    )
                elif scenario in (
                    "filled_terminal",
                    "canceled_terminal",
                    "duplicate_after_terminal",
                ):
                    state = "canceled" if scenario == "canceled_terminal" else "filled"
                    store.order_status(
                        proposal.intent_id, "VERIFIED", venue_state=state
                    )
                    if store.unresolved():
                        raise ValueError(
                            "verified terminal record should leave unresolved set"
                        )
                    events.append(
                        {
                            "step": "injected_terminal_query",
                            "backend_method": "Store.order_status",
                            "stored_status": "VERIFIED",
                            "fixture_venue_state": state,
                        }
                    )
                    if scenario == "duplicate_after_terminal":
                        duplicate = store.duplicate(proposal.intent_id)
                        if store.claim(proposal, "fixture-retry", "MOCK"):
                            raise ValueError("duplicate claim unexpectedly accepted")
                        events.append(
                            {
                                "step": "same_intent_retry",
                                "backend_method": "Store.claim",
                                "accepted": False,
                                "duplicate_from_journal": duplicate,
                            }
                        )
                    else:
                        intent_requested = False
                else:
                    raise ValueError("unrecognized allowlisted offline scenario")
            unresolved = bool(store.unresolved())
            assessed = proposal if duplicate else new_proposal
            if not intent_requested:
                assessed = models.Proposal(
                    action="NO_TRADE",
                    symbol="BTC-USDT",
                    quantity="0",
                    intent_id="fixture-monitor",
                    summary="Offline monitoring only",
                )
            gate = policy.check(
                observation(models),
                stub(models),
                assessed,
                now=NOW,
                source_mode="MOCK",
                approval_available=True,
                unresolved=unresolved,
                duplicate=duplicate,
            )
            events.append(
                {
                    "step": "gate",
                    "backend_method": "policy.check",
                    "approved": gate.approved,
                    "reasons": gate.reasons,
                }
            )
            return {
                "scenario": scenario,
                "quantity": quantity,
                "events": events,
                "context_updates": {
                    "unknown_order": unknown_order,
                    "duplicate_intent": duplicate,
                    "api_timeout": api_timeout,
                    "intent_requested": intent_requested,
                },
                "derived_from_store": ["duplicate_intent"]
                + (["unknown_order"] if scenario == "submit_timeout_unknown" else []),
                "pending_journal": unresolved,
                "backend_gate": gate.model_dump(mode="json"),
                "origin": "OFFLINE_BACKEND_TEST",
                "injected_exchange_events": True,
                "execution_component_loaded": False,
                "actual_exchange_receipt": False,
                "laya_classification_is_stub": True,
                "full_agent_reconciliation_test": False,
            }
        finally:
            store.close()


LIFECYCLE_SCENARIOS = (
    "read_timeout_before_submit",
    "submit_timeout_unknown",
    "place_ack_only",
    "active_live",
    "active_partial",
    "cancel_ack_only",
    "filled_terminal",
    "canceled_terminal",
    "duplicate_after_terminal",
    "new_intent_while_pending",
)


def gate_probes(modules):
    """Fields not represented by the classifier remain diagnostic-only evidence."""
    models, policy = modules["models"], modules["policy"]
    specs = [
        ("valid_reference", {}, "0.0001", "BUY", None),
        ("minimum_below", {}, "0.00000999", "BUY", "invalid_quantity"),
        ("minimum_exact", {}, "0.00001", "BUY", None),
        ("minimum_above", {}, "0.00001001", "BUY", None),
        ("lot_misaligned", {}, "0.000100001", "BUY", "invalid_quantity"),
        ("order_notional_excess", {}, "0.001", "BUY", "excess_order_notional"),
        (
            "quote_balance_empty",
            {"quote_available": "0"},
            "0.0001",
            "BUY",
            "insufficient_quote",
        ),
        (
            "base_balance_empty",
            {"base_available": "0"},
            "0.0001",
            "SELL",
            "insufficient_base",
        ),
        (
            "exposure_excess",
            {"exposure_quote": "1001"},
            "0.0001",
            "BUY",
            "excess_exposure",
        ),
        ("crossed_quotes", {"bid": "50002"}, "0.0001", "BUY", "crossed_quotes"),
        (
            "account_timestamp_stale",
            {"account_observed_at": NOW - timedelta(seconds=30)},
            "0.0001",
            "BUY",
            "stale_account",
        ),
    ]
    result = []
    for family, changes, quantity, side, expected_reason in specs:
        obs = observation(models, **changes)
        proposal = models.Proposal(
            action=side,
            symbol="BTC-USDT",
            quantity=quantity,
            intent_id="fixture-probe",
            summary="Offline gate probe",
        )
        gate = policy.check(
            obs,
            stub(models),
            proposal,
            now=NOW,
            source_mode="MOCK",
            approval_available=True,
            unresolved=False,
            duplicate=False,
        )
        if expected_reason is None and not gate.approved:
            raise ValueError("valid probe unexpectedly blocked")
        if expected_reason and expected_reason not in gate.reasons:
            raise ValueError("required deterministic veto missing")
        result.append(
            {
                "scenario": family,
                "observation": obs.model_dump(mode="json"),
                "proposal": {"action": side, "quantity": quantity},
                "backend_gate": gate.model_dump(mode="json"),
                "model_training_candidate": False,
                "reason_excluded": "Existing normalized model input lacks min/lot/price/balance/account-time context",
                "origin": "OFFLINE_BACKEND_TEST",
                "laya_is_stub": True,
                "actual_exchange_receipt": False,
            }
        )
    return result
