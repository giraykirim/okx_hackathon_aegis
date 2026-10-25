"""SHADOW exit assessment: owned fills -> Agent.cycle -> persisted record -> read-only API.

Offline only: synthetic schema-2 fills, temporary SQLite, stubbed venue/model calls. The
assessment is advisory capacity data; these tests prove it never reaches claim/place.
"""

import json
import sqlite3
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_policy import inputs
from test_position_lifecycle import fill

from aegis.models import Decision
from aegis.settings import Settings
from aegis.store import Store

FIXTURE = Path(__file__).resolve().parents[2] / "frontend/src/__tests__/fixtures/exit-shadow-current.json"


def demo_settings(path, **extra):
    return Settings(
        _env_file=None,
        source_mode="OKX_DEMO",
        db_path=path,
        demo_enabled=True,
        demo_region_confirmed=True,
        okx_demo_api_key="test-demo",
        okx_demo_secret_key="test-secret",
        okx_demo_passphrase="test-pass",
        **extra,
    )


def forbid(calls, name):
    def call(*args, **kwargs):
        calls.append(name)
        raise AssertionError(f"{name} must not be called by the shadow exit flow")

    return call


def demo_agent(tmp_path, monkeypatch, *, action="NO_TRADE", market=None, observe_error=False,
               reason_error=False, db="shadow.sqlite3"):
    from aegis.agent import Agent

    agent = Agent(demo_settings(tmp_path / db))

    async def observe():
        if observe_error:
            raise RuntimeError("venue unavailable")
        observation = inputs()[0]
        return observation.model_copy(update={"account_observed_at": observation.observed_at, **(market or {})})

    async def trend():
        return {"bar": "15m"}

    async def reason(*args, **kwargs):
        if reason_error:
            raise RuntimeError("EVREN unavailable")
        quantity = Decimal(0) if action == "NO_TRADE" else Decimal("0.0001")
        return inputs()[2].model_copy(update={"action": action, "quantity": quantity})

    async def classify(*args, **kwargs):
        return inputs()[1]

    monkeypatch.setattr(agent.atk, "observe", observe)
    monkeypatch.setattr(agent.atk, "trend", trend)
    monkeypatch.setattr(agent.models, "reason", reason)
    monkeypatch.setattr(agent.models, "classify", classify)
    return agent


def forbid_execution(agent, monkeypatch, *, reconcile=True):
    calls = []
    monkeypatch.setattr(agent.atk, "place", forbid(calls, "place"))
    monkeypatch.setattr(agent.store, "claim", forbid(calls, "claim"))
    if reconcile:
        monkeypatch.setattr(agent.atk, "reconcile", forbid(calls, "reconcile"))
    return calls


def seed(store, ref, side, qty, fee="0", ccy="BTC", t=0, status="VERIFIED"):
    """A verified agent-owned fill through the real intent/client/venue ownership checks."""
    proposal = inputs()[2].model_copy(update={"action": side.upper(), "quantity": Decimal("0.0001"), "intent_id": ref})
    client = ("shadow-" + ref).ljust(32, "0")[:32]
    assert store.claim(proposal, client, "OKX_DEMO")
    store.order_status(ref, status, "ord-" + ref, "filled")
    store.record_fill(ref, fill(ref, client, side, qty, "50000", fee, ccy, t))
    return client


def proposal_of(store):
    return store.latest_exit_assessment()["proposal"]


def shape(value):
    if isinstance(value, dict):
        return {key: shape(item) for key, item in value.items()}
    if isinstance(value, list):
        return "list"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return "number"
    return type(value).__name__


@pytest.mark.asyncio
async def test_owned_buy_cycle_persists_shadow_and_real_api_serves_it_after_restart(tmp_path, monkeypatch):
    agent = demo_agent(tmp_path, monkeypatch)
    seed(agent.store, "b1", "buy", "0.0002", fee="-0.0000002")
    calls = forbid_execution(agent, monkeypatch)
    decision = await agent.cycle()
    assert decision.proposed_action == "NO_TRADE" and decision.execution_status == "NOT_SENT"
    assert calls == []
    record = agent.store.latest_exit_assessment()
    assert record["cycle_id"] == agent.cycle_id and record["run_id"] == agent.run_id
    assert record["source_mode"] == "OKX_DEMO" and record["orders_sent"] is False
    assert record["fraction_semantics"] == "full_close_capacity_not_a_sell_signal"
    await agent.close()

    # Restart: a new app process reads the persisted record; nothing is recomputed.
    from aegis.app import create_app

    with TestClient(create_app(demo_settings(tmp_path / "shadow.sqlite3"))) as api:
        body = api.get("/api/metrics/exit-shadow").json()
    assert body["state"] == "CURRENT" and body["current"] is True and body["not_current_reasons"] == []
    assert body["mode"] == "SHADOW" and body["orders_sent"] is False and body["executable"] is False
    proposal = body["assessment"]["proposal"]
    assert proposal["status"] == "PROPOSE_CLOSE" and proposal["requested_fraction"] == "1"
    assert (proposal["owned_net_btc"], proposal["proposed_sell_btc"], proposal["remaining_btc"]) == (
        "0.00019980", "0.00019980", "0.00000000"
    )
    assert proposal["executable"] is False and proposal["order_adapter"] is None
    assert proposal["entry_edge_gate_applies"] is False
    assert body["assessment"]["inventory_basis"]["owned_fill_count"] == 1

    # The dashboard fixture is this exact API contract (shape plus deterministic values).
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert shape(body) == shape(fixture)
    for key in ("state", "mode", "orders_sent", "executable", "current", "not_current_reasons"):
        assert body[key] == fixture[key]
    for key in ("status", "reasons", "owned_net_btc", "sellable_btc", "proposed_sell_btc", "remaining_btc",
                "lot_size", "min_size", "reference_bid", "requested_fraction", "executable", "order_adapter"):
        assert proposal[key] == fixture["assessment"]["proposal"][key], key


@pytest.mark.asyncio
@pytest.mark.parametrize("action,reason_error", [("NO_TRADE", False), ("BUY", False), ("NO_TRADE", True)])
async def test_no_trade_missing_edge_or_model_failure_do_not_stop_shadow(tmp_path, monkeypatch, action, reason_error):
    agent = demo_agent(tmp_path, monkeypatch, action=action, reason_error=reason_error)
    seed(agent.store, "b1", "buy", "0.0002", fee="-0.0000002")
    calls = forbid_execution(agent, monkeypatch)
    assert agent.trade_edge(None) == (None, None)  # rejected A/P1 edge stays unavailable
    if reason_error:
        with pytest.raises(RuntimeError):
            await agent.cycle()
    else:
        decision = await agent.cycle()
        assert decision.execution_status == "NOT_SENT" and not decision.risk_approved
        if action == "BUY":
            # Entry cost gate still routes the BUY to REVIEW; the exit shadow is not hidden by it.
            assert "cost_edge_source_missing" in decision.risk_reasons
    assert calls == []
    proposal = proposal_of(agent.store)
    assert proposal["status"] == "PROPOSE_CLOSE" and proposal["proposed_sell_btc"] == "0.00019980"
    await agent.close()


@pytest.mark.asyncio
async def test_foreign_balance_and_unowned_fills_never_create_inventory(tmp_path, monkeypatch):
    agent = demo_agent(tmp_path, monkeypatch, market={"base_available": Decimal("1.5")})
    agent.store.record_fill("foreign", fill("foreign", "x" * 32, "buy", "0.5", "50000", "0", "BTC", 0))
    calls = forbid_execution(agent, monkeypatch)
    await agent.cycle()
    record = agent.store.latest_exit_assessment()
    assert record["proposal"]["status"] == "NO_EXIT" and record["proposal"]["reasons"] == ["no_owned_inventory"]
    assert record["proposal"]["owned_net_btc"] == "0.00000000" and record["proposal"]["proposed_sell_btc"] is None
    assert record["inventory_basis"]["owned_fill_count"] == 0
    assert record["inventory_basis"]["excluded_unowned_fills"] == 1
    assert calls == []
    await agent.close()


@pytest.mark.asyncio
async def test_partial_fill_and_repeated_reconcile_never_double_count(tmp_path, monkeypatch):
    agent = demo_agent(tmp_path, monkeypatch)
    ref, client = "p1", "partial".ljust(32, "0")
    pending = inputs()[2].model_copy(update={"intent_id": ref, "quantity": Decimal("0.0001")})
    saved = Decision(id=client, run_id="r", symbol="BTC-USDT", proposed_action="BUY", laya_label="CONTINUE",
                     laya_confidence=1, llm_summary="t", evidence_ids=[], risk_approved=True, risk_reasons=[],
                     execution_status="PENDING", source_mode="OKX_DEMO", intent_id=ref, quantity="0.0001",
                     limit_price="50100")
    assert agent.store.claim(pending, client, "OKX_DEMO", pending_decision=saved)
    reads = iter([("PENDING", "0.00005", "partially_filled")] * 2 + [("VERIFIED", "0.00008", "canceled")])

    async def reconcile(*args):
        status, qty, state = next(reads)
        agent.atk.last_fill = fill(ref, client, "buy", qty, "50000", "0", "BTC", 0, state=state)
        return status, "ord-" + ref, state

    monkeypatch.setattr(agent.atk, "reconcile", reconcile)
    calls = forbid_execution(agent, monkeypatch, reconcile=False)
    statuses = []
    for _ in range(4):  # partial, repeated partial, final, then no further reconcile
        await agent.cycle()
        statuses.append(proposal_of(agent.store)["status"])
    assert statuses == ["REVIEW", "REVIEW", "PROPOSE_CLOSE", "PROPOSE_CLOSE"]
    assert len(agent.store.fills()) == 1
    proposal = proposal_of(agent.store)
    assert proposal["owned_net_btc"] == proposal["proposed_sell_btc"] == "0.00008000"
    count = agent.store.db.execute("SELECT COUNT(*) FROM exit_assessments").fetchone()[0]
    assert count == 4 and calls == []
    await agent.close()


@pytest.mark.asyncio
async def test_unresolved_order_or_missing_fee_gives_review_without_quantity(tmp_path, monkeypatch):
    agent = demo_agent(tmp_path, monkeypatch)
    seed(agent.store, "b1", "buy", "0.0002")
    seed(agent.store, "open", "sell", "0.0001", status="PENDING")  # no saved decision -> stays UNKNOWN
    calls = forbid_execution(agent, monkeypatch)
    await agent.cycle()
    proposal = proposal_of(agent.store)
    assert proposal["status"] == "REVIEW" and "unresolved_prior_order" in proposal["reasons"]
    assert proposal["proposed_sell_btc"] is None and calls == []
    await agent.close()

    agent = demo_agent(tmp_path, monkeypatch, db="fee.sqlite3")
    seed(agent.store, "b1", "buy", "0.0002")
    seed(agent.store, "s1", "sell", "0.0001", fee=None, ccy="USDT", t=10)
    calls = forbid_execution(agent, monkeypatch)
    await agent.cycle()
    proposal = proposal_of(agent.store)
    assert proposal["status"] == "REVIEW" and "inventory_uncertain" in proposal["reasons"]
    assert proposal["owned_net_btc"] is None and proposal["proposed_sell_btc"] is None and calls == []
    await agent.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("kwargs,reason", [
    ({"market": {"observed_at": inputs()[3] - timedelta(minutes=5)}}, "stale_market_data"),
    ({"observe_error": True}, "no_market_data"),
])
async def test_stale_or_missing_market_gives_review(tmp_path, monkeypatch, kwargs, reason):
    agent = demo_agent(tmp_path, monkeypatch, **kwargs)
    seed(agent.store, "b1", "buy", "0.0002")
    calls = forbid_execution(agent, monkeypatch)
    await agent.cycle()
    record = agent.store.latest_exit_assessment()
    assert record["proposal"]["status"] == "REVIEW" and reason in record["proposal"]["reasons"]
    assert record["proposal"]["proposed_sell_btc"] is None and calls == []
    assert (record["market_source"] is None) == (reason == "no_market_data")
    await agent.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("fills,market,expected", [
    ([("b1", "buy", "0.000025", "0")], {"lot_size": Decimal("0.00001")},
     ("PROPOSE_CLOSE", "0.00002000", "0.00000500", [])),
    ([("b1", "buy", "0.000025", "0")], {"min_size": Decimal("0.0001")},
     ("NO_EXIT", None, "0.00002500", ["below_min_size"])),
    ([("b1", "buy", "0.0001", "-0.00000000123")], {},
     ("PROPOSE_CLOSE", "0.00009999", "0.00000000877", [])),
    ([("b1", "buy", "0.0002", "0"), ("s1", "sell", "0.0002", "-0.01")], {},
     ("NO_EXIT", None, None, ["no_owned_inventory"])),
])
async def test_lot_minimum_dust_and_true_zero_inventory(tmp_path, monkeypatch, fills, market, expected):
    agent = demo_agent(tmp_path, monkeypatch, market=market)
    for t, (ref, side, qty, fee) in enumerate(fills):
        seed(agent.store, ref, side, qty, fee=fee, ccy="BTC" if side == "buy" else "USDT", t=t)
    calls = forbid_execution(agent, monkeypatch)
    await agent.cycle()
    record = agent.store.latest_exit_assessment()
    proposal = record["proposal"]
    assert (proposal["status"], proposal["proposed_sell_btc"], proposal["remaining_btc"], proposal["reasons"]) == expected
    if expected[3] == ["no_owned_inventory"]:  # verified zero, not a missing assessment
        assert proposal["owned_net_btc"] == "0.00000000" and record["inventory_basis"]["owned_fill_count"] == 2
    assert calls == []
    await agent.close()


@pytest.mark.asyncio
async def test_restart_keeps_latest_but_age_mode_or_inventory_change_is_not_current(tmp_path, monkeypatch):
    agent = demo_agent(tmp_path, monkeypatch)
    seed(agent.store, "b1", "buy", "0.0002")
    await agent.cycle()
    await agent.close()

    store = Store(tmp_path / "shadow.sqlite3", [])
    record = store.latest_exit_assessment()
    at = datetime.fromisoformat(record["computed_at"])
    view = store.exit_shadow(now=at + timedelta(seconds=1), source_mode="OKX_DEMO")
    assert view["state"] == "CURRENT" and view["assessment"]["assessment_id"] == record["assessment_id"]
    old = store.exit_shadow(now=at + timedelta(seconds=120), source_mode="OKX_DEMO")
    assert old["state"] == "STALE" and old["current"] is False
    assert old["not_current_reasons"] == ["assessment_stale", "market_data_expired"]
    moved = store.exit_shadow(now=at + timedelta(seconds=1), source_mode="MARKET_ONLY")
    assert moved["state"] == "STALE" and moved["not_current_reasons"] == ["source_mode_changed"]
    seed(store, "b2", "buy", "0.0001", t=5)
    changed = store.exit_shadow(now=at + timedelta(seconds=1), source_mode="OKX_DEMO")
    assert changed["state"] == "SUPERSEDED" and "inventory_changed_since_assessment" in changed["not_current_reasons"]

    # Re-saving one cycle replaces its row; history stays bounded and the latest survives.
    store.record_exit_assessment({**record, "assessment_id": "again"})
    assert store.db.execute("SELECT COUNT(*) FROM exit_assessments").fetchone()[0] == 1
    for i in range(5):
        store.record_exit_assessment({**record, "cycle_id": f"c{i}", "assessment_id": f"a{i}"}, keep=3)
    assert store.db.execute("SELECT COUNT(*) FROM exit_assessments").fetchone()[0] == 3
    assert store.latest_exit_assessment()["assessment_id"] == "a4"
    store.close()


def market_time(record):
    return datetime.fromisoformat(record["proposal"]["market_observed_at"])


@pytest.mark.asyncio
async def test_market_age_is_judged_separately_from_record_age(tmp_path, monkeypatch):
    agent = demo_agent(tmp_path, monkeypatch)
    seed(agent.store, "b1", "buy", "0.0002")
    await agent.cycle()
    record = agent.store.latest_exit_assessment()
    assert record["proposal"]["status"] == "PROPOSE_CLOSE" and record["market_max_age_seconds"] == 15
    observed = market_time(record)
    edge = agent.store.exit_shadow(now=observed + timedelta(seconds=15), source_mode="OKX_DEMO")
    assert edge["state"] == "CURRENT" and edge["market_age_seconds"] == 15.0 and edge["market_dependent"] is True
    expired = agent.store.exit_shadow(now=observed + timedelta(seconds=16), source_mode="OKX_DEMO")
    # The record itself is ~16s old (inside its 60s bound); only the market basis has expired.
    assert expired["age_seconds"] < expired["max_age_seconds"]
    assert expired["state"] == "STALE" and expired["current"] is False
    assert expired["not_current_reasons"] == ["market_data_expired"]
    assert expired["market_age_seconds"] == 16.0 and expired["market_max_age_seconds"] == 15
    await agent.close()


@pytest.mark.asyncio
async def test_observation_already_aged_at_computation_expires_by_market_time(tmp_path, monkeypatch):
    agent = demo_agent(tmp_path, monkeypatch, market={"observed_at": inputs()[3] - timedelta(seconds=14)})
    seed(agent.store, "b1", "buy", "0.0002")
    await agent.cycle()
    record = agent.store.latest_exit_assessment()
    assert record["proposal"]["status"] == "PROPOSE_CLOSE"  # valid at computation (14s < 15s)
    observed, computed = market_time(record), datetime.fromisoformat(record["computed_at"])
    assert (computed - observed).total_seconds() >= 14
    fresh = agent.store.exit_shadow(now=observed + timedelta(seconds=14.5), source_mode="OKX_DEMO")
    assert fresh["state"] == "CURRENT"
    later = agent.store.exit_shadow(now=computed + timedelta(seconds=2), source_mode="OKX_DEMO")
    assert later["age_seconds"] <= 2.0  # a young record does not refresh an old observation
    assert later["state"] == "STALE" and later["not_current_reasons"] == ["market_data_expired"]
    await agent.close()


@pytest.mark.asyncio
async def test_restarted_api_does_not_serve_expired_market_capacity_as_current(tmp_path, monkeypatch):
    from aegis.app import create_app

    agent = demo_agent(tmp_path, monkeypatch)
    seed(agent.store, "b1", "buy", "0.0002")
    await agent.cycle()
    observed = market_time(agent.store.latest_exit_assessment())
    await agent.close()

    with TestClient(create_app(demo_settings(tmp_path / "shadow.sqlite3"))) as api:
        monkeypatch.setattr("aegis.store.utcnow", lambda: observed + timedelta(seconds=15))
        assert api.get("/api/metrics/exit-shadow").json()["state"] == "CURRENT"
        monkeypatch.setattr("aegis.store.utcnow", lambda: observed + timedelta(seconds=16))
        body = api.get("/api/metrics/exit-shadow").json()
    assert body["state"] == "STALE" and body["current"] is False
    assert body["not_current_reasons"] == ["market_data_expired"]


@pytest.mark.asyncio
@pytest.mark.parametrize("fills,status,reason", [
    ([("b1", "buy", "0.0002", "VERIFIED"), ("s1", "sell", "0.0002", "VERIFIED")], "NO_EXIT", "no_owned_inventory"),
    ([("b1", "buy", "0.0002", "VERIFIED"), ("open", "sell", "0.0001", "PENDING")], "REVIEW", "unresolved_prior_order"),
])
async def test_market_independent_outcomes_stay_current_after_market_bound(tmp_path, monkeypatch, fills, status, reason):
    agent = demo_agent(tmp_path, monkeypatch)
    for t, (ref, side, qty, state) in enumerate(fills):
        seed(agent.store, ref, side, qty, ccy="BTC" if side == "buy" else "USDT", t=t, status=state)
    await agent.cycle()
    record = agent.store.latest_exit_assessment()
    assert record["proposal"]["status"] == status and reason in record["proposal"]["reasons"]
    view = agent.store.exit_shadow(now=market_time(record) + timedelta(seconds=30), source_mode="OKX_DEMO")
    assert view["state"] == "CURRENT" and view["not_current_reasons"] == []
    assert view["market_dependent"] is False and view["market_age_seconds"] >= 30
    await agent.close()


@pytest.mark.asyncio
async def test_market_dependent_record_without_market_bound_fails_closed(tmp_path, monkeypatch):
    agent = demo_agent(tmp_path, monkeypatch)
    seed(agent.store, "b1", "buy", "0.0002")
    await agent.cycle()
    record = agent.store.latest_exit_assessment()
    legacy = {k: v for k, v in record.items() if k != "market_max_age_seconds"}
    agent.store.record_exit_assessment({**legacy, "cycle_id": "legacy"})
    view = agent.store.exit_shadow(now=market_time(record) + timedelta(seconds=1), source_mode="OKX_DEMO")
    assert view["state"] == "STALE" and view["not_current_reasons"] == ["market_age_bound_missing"]
    await agent.close()


def test_existing_database_without_exit_table_opens_compatibly(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    legacy = sqlite3.connect(path)
    legacy.executescript("""
        CREATE TABLE events (seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE, body TEXT);
        CREATE TABLE decisions (seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE, body TEXT);
        INSERT INTO events(id, body) VALUES ('e1', '{"kept": true}');
    """)
    legacy.commit()
    legacy.close()
    store = Store(path, [])
    assert store.exit_shadow()["state"] == "NO_ASSESSMENT" and store.exit_shadow()["assessment"] is None
    assert store.events() == [{"kept": True}]
    store.close()


def test_api_read_is_side_effect_free_and_absent_from_public_surface(tmp_path, monkeypatch):
    from aegis.app import create_app
    from aegis.public_app import create_public_app

    with TestClient(create_app(demo_settings(tmp_path / "read.sqlite3"))) as api:
        empty = api.get("/api/metrics/exit-shadow")
        assert empty.status_code == 200 and empty.json()["state"] == "NO_ASSESSMENT"
        agent = api.app.state.agent
        seed(agent.store, "b1", "buy", "0.0002")
        agent.cycle_id = "manual-cycle"
        agent.record_exit_shadow(inputs()[0])
        calls = forbid_execution(agent, monkeypatch)
        for target, name in ((agent, "cycle"), (agent, "record_exit_shadow"), (agent.atk, "observe"),
                             (agent.store, "record_exit_assessment"), (agent.store, "record_fill")):
            monkeypatch.setattr(target, name, forbid(calls, name))
        monkeypatch.setattr("aegis.agent.propose_exit_from_store", forbid(calls, "propose_exit_from_store"))

        def counts():
            return [agent.store.db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                    for t in ("events", "decisions", "intents", "fills", "exit_assessments")]

        before = counts()
        for _ in range(3):
            body = api.get("/api/metrics/exit-shadow").json()
            assert body["state"] == "CURRENT" and body["assessment"]["cycle_id"] == "manual-cycle"
        assert counts() == before and calls == []

    surface = create_public_app(Settings(_env_file=None, db_path=tmp_path / "public.sqlite3",
                                         service_api_key="unit-service"))
    with TestClient(surface) as public:
        assert public.get("/api/metrics/exit-shadow").status_code == 404


@pytest.mark.asyncio
async def test_shadow_record_never_reaches_execution_and_failures_stay_isolated(tmp_path, monkeypatch):
    agent = demo_agent(tmp_path, monkeypatch)
    seed(agent.store, "b1", "buy", "0.0002")
    calls = forbid_execution(agent, monkeypatch)
    monkeypatch.setattr(agent.store, "record_fill", forbid(calls, "record_fill"))
    monkeypatch.setattr(agent.models, "reason", forbid(calls, "reason"))
    agent.cycle_id = "direct"
    agent.record_exit_shadow(inputs()[0])
    assert proposal_of(agent.store)["status"] == "PROPOSE_CLOSE" and calls == []

    def broken(*args, **kwargs):
        raise ArithmeticError("corrupt ledger")

    monkeypatch.setattr("aegis.agent.propose_exit_from_store", broken)
    agent.cycle_id = "broken"
    agent.record_exit_shadow(inputs()[0])
    proposal = proposal_of(agent.store)
    assert proposal["status"] == "REVIEW" and proposal["reasons"] == ["exit_assessment_failed", "ArithmeticError"]
    assert proposal["proposed_sell_btc"] is None and calls == []
    await agent.close()


@pytest.mark.asyncio
async def test_mock_mode_never_uses_scripted_market_as_venue_constraints(tmp_path):
    from aegis.agent import Agent

    agent = Agent(Settings(_env_file=None, source_mode="MOCK", db_path=tmp_path / "mock.sqlite3"))
    await agent.cycle()
    record = agent.store.latest_exit_assessment()
    assert record["source_mode"] == "MOCK" and record["market_source"] == "MOCK_SCRIPTED_NOT_USED"
    assert record["proposal"]["status"] == "NO_EXIT" and record["proposal"]["lot_size"] is None
    await agent.close()
