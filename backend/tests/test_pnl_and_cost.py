"""PnL accounting and pre-trade cost gate behaviour (offline, isolated temporary databases)."""

from datetime import timedelta
from decimal import Decimal

import pytest
from test_policy import allow_costs, inputs

from aegis.cost_gate import CostConfig, EdgeEstimate, ExitPlan, evaluate
from aegis.models import Observation, Proposal, utcnow
from aegis.pnl import compute
from aegis.settings import Settings
from aegis.store import Store

T0 = 1792000000000  # venue fillTime base (ms)


def fill(side, qty, px, fee="0", fee_ccy="USDT", t=0, ref=None, **extra):
    ref = ref or f"{side}-{t}"
    return {
        "schema": 2,
        "ord_id": ref,
        "intent_id": ref,
        "side": side,
        "ord_type": "ioc",
        "filled_qty": qty,
        "avg_price": px,
        "fee": fee,
        "fee_ccy": fee_ccy,
        "rebate": "",
        "rebate_ccy": None,
        "fill_time_ms": str(T0 + t * 1000),
        "source_mode": "OKX_DEMO",
        **extra,
    }


# --- accounting ----------------------------------------------------------------------------


def test_a_fee_free_round_trip_full_close_needs_no_mark():
    out = compute([fill("buy", "1", "100", t=0), fill("sell", "1", "110", t=1)], "X-USDT", None)
    assert (out["realized"], out["net"], out["inventory_qty"]) == ("10.00000000", "10.00000000", "0.00000000")
    assert out["unrealized"] == "0.00000000" and out["complete"] and out["issues"] == []


def test_b_base_currency_fee_reduces_inventory_not_cash():
    out = compute([fill("buy", "0.1", "40000", fee="-0.0001", fee_ccy="BTC")], "BTC-USDT", Decimal("50000"))
    assert out["inventory_qty"] == "0.09990000"
    assert out["cost_basis"] == "4000.00000000"
    assert out["net"] == "995.00000000"
    assert out["fee_breakdown"] == {"BTC": "-0.00010000"}
    assert out["fees"] == "4.00000000"  # informational quote value, not deducted again


def test_c_positive_rebate_is_income_not_cost():
    rebate = fill("buy", "1", "100", fee="0", fee_ccy="BTC", rebate="1", rebate_ccy="USDT")
    out = compute([rebate], "BTC-USDT", Decimal("100"))
    assert out["net"] == "1.00000000" and out["fees"] == "-1.00000000"
    signed = compute([fill("buy", "1", "100", fee="1", fee_ccy="USDT")], "BTC-USDT", Decimal("100"))
    assert signed["net"] == "1.00000000"  # the sign of fee is preserved, never abs()


def test_partial_sell_keeps_average_cost_consistent():
    out = compute(
        [fill("buy", "2", "100", t=0), fill("sell", "0.5", "120", fee="-0.6", t=1)],
        "BTC-USDT",
        Decimal("110"),
    )
    assert out["realized"] == "9.40000000"
    assert out["inventory_qty"] == "1.50000000" and out["average_cost"] == "100.00000000"
    assert out["unrealized"] == "15.00000000" and out["net"] == "24.40000000"


def test_quote_fee_on_buy_is_capitalized_once():
    out = compute([fill("buy", "1", "100", fee="-0.1")], "BTC-USDT", Decimal("100"))
    assert out["cost_basis"] == "100.10000000" and out["net"] == "-0.10000000"
    assert out["fees"] == "0.10000000"


def test_gross_gain_can_be_a_net_loss_after_fees():
    out = compute(
        [
            fill("buy", "1", "100", fee="-0.002", fee_ccy="BTC", t=0),
            fill("sell", "0.998", "100.1", fee="-0.2", t=1),
        ],
        "BTC-USDT",
        None,
    )
    assert out["inventory_qty"] == "0.00000000"
    assert Decimal(out["realized"]) < 0 and out["net"] == out["realized"] == "-0.30020000"


@pytest.mark.parametrize(
    "record,issue",
    [
        (fill("buy", "1", "100", fee=None), "missing_fee:"),
        (fill("buy", "1", "100", fee="-0.01", fee_ccy="OKB"), "unconverted_fee_currency:OKB"),
        (fill("buy", "1", "100", fee="-0.01", fee_ccy=None), "missing_fee_currency:"),
    ],
)
def test_missing_or_unconvertible_fee_is_never_zero(record, issue):
    out = compute([record], "BTC-USDT", Decimal("100"))
    assert out["net"] is None and not out["complete"]
    assert any(i.startswith(issue) for i in out["issues"])


def test_missing_mark_with_open_inventory_reports_null_net():
    out = compute([fill("buy", "1", "100")], "BTC-USDT", None)
    assert out["unrealized"] is None and out["net"] is None and "mark_price_missing" in out["issues"]


def test_fills_are_ordered_by_venue_time_not_arrival():
    late_recorded_buy = fill("buy", "1", "100", t=0)
    early_recorded_sell = fill("sell", "1", "105", t=5)
    out = compute([early_recorded_sell, late_recorded_buy], "BTC-USDT", None)
    assert out["unmatched_sell_qty"] == "0.00000000" and out["realized"] == "5.00000000"
    assert [row["side"] for row in out["ledger"]] == ["buy", "sell"]


def test_sell_beyond_agent_inventory_is_not_profit():
    out = compute([fill("buy", "1", "100", t=0), fill("sell", "3", "200", t=1)], "BTC-USDT", None)
    assert out["realized"] == "100.00000000" and out["unmatched_sell_qty"] == "2.00000000"
    assert any(w.startswith("sell_exceeds_agent_inventory") for w in out["warnings"])


def test_maker_sell_rebate_overlap_is_flagged_not_guessed():
    record = fill("sell", "1", "100", ord_type="limit", rebate="0.1", rebate_ccy="BTC", t=1)
    out = compute([fill("buy", "1", "90", t=0), record], "BTC-USDT", None)
    assert out["net"] is None and any(i.startswith("ambiguous_maker_sell") for i in out["issues"])


# --- persistence, ownership, reconcile --------------------------------------------------------


def own(store, ref):
    proposal = Proposal(action="BUY", symbol="BTC-USDT", quantity="0.0001", intent_id=ref, summary="t")
    client = ref.ljust(32, "0")[:32]
    assert store.claim(proposal, client, "OKX_DEMO")
    store.order_status(ref, "VERIFIED", "ord-" + ref, "filled")
    return client


def test_reconcile_repeats_and_partial_updates_never_double_count(tmp_path):
    store = Store(tmp_path / "fills.sqlite3", [])
    client = own(store, "i1")
    base = dict(intent_id="i1", decision_id=client, ord_id="ord-i1")
    store.record_fill("i1", fill("buy", "0.00005", "100", **base))
    store.record_fill("i1", fill("buy", "0.0001", "100", **base))
    store.record_fill("i1", fill("buy", "0.0001", "100", **base))
    store.record_fill("i1", fill("buy", "0.00005", "100", **base))  # stale read cannot shrink
    store.save_mark(inputs()[0].model_copy(update={"price": Decimal("100")}))
    pnl = store.demo_pnl()
    assert pnl["fill_count"] == 1 and pnl["inventory_qty"] == "0.00010000"
    store.close()


def test_only_owned_demo_fills_count_and_mark_survives_restart(tmp_path):
    path = tmp_path / "owned.sqlite3"
    store = Store(path, [])
    client = own(store, "mine")
    store.record_fill("mine", fill("buy", "0.1", "40000", fee="-0.0001", fee_ccy="BTC",
                                   intent_id="mine", decision_id=client, ord_id="ord-mine"))
    store.record_fill("stray", fill("buy", "5", "1", intent_id="stray", decision_id="x", ord_id="o"))
    store.record_fill("mock", fill("buy", "5", "1", intent_id="mine", decision_id=client,
                                   ord_id="ord-mine", source_mode="MOCK"))
    observation = inputs()[0]
    store.save_mark(observation)
    store.close()

    reopened = Store(path, [])
    pnl = reopened.demo_pnl(now=observation.observed_at + timedelta(seconds=5))
    assert pnl["excluded_unowned_fills"] == 2 and pnl["fill_count"] == 1
    assert pnl["valuation_status"] == "CURRENT_MARK" and pnl["net"] == "995.00000000"
    assert pnl["mark"]["observed_at"] == observation.observed_at.isoformat()
    stale = reopened.demo_pnl(now=observation.observed_at + timedelta(hours=2))
    assert stale["valuation_status"] == "STALE_MARK" and stale["mark"]["stale"] is True
    reopened.close()


@pytest.mark.asyncio
async def test_atk_reconcile_keeps_venue_fee_sign_time_and_rebate(monkeypatch):
    from aegis.atk import ATK

    atk = ATK(Settings(_env_file=None))
    proposal = inputs()[2]

    async def read(*args):
        return [dict(instId="BTC-USDT", clOrdId="a" * 32, side="buy", sz="0.0001", ordId="o1",
                     ordType="ioc", tdMode="cash", px="50100", state="filled", avgPx="50000",
                     accFillSz="0.0001", fee="", feeCcy="BTC", rebate="", rebateCcy="USDT",
                     fillTime="1792000000123", uTime="1792000000200", cTime="1792000000000")]

    monkeypatch.setattr(atk, "call", read)
    await atk.reconcile(proposal, "a" * 32, Decimal("50100"))
    assert atk.last_fill["fee"] is None  # "" is missing, never "0"
    assert atk.last_fill["fill_time_ms"] == "1792000000123" and atk.last_fill["schema"] == 2
    assert "filled_at" not in atk.last_fill


@pytest.mark.asyncio
async def test_backfill_covers_every_verified_intent_and_refreshes_legacy(tmp_path, monkeypatch):
    from aegis.agent import Agent
    from aegis.models import Decision

    agent = Agent(Settings(_env_file=None, source_mode="OKX_DEMO", db_path=tmp_path / "bf.sqlite3"))
    store = agent.store
    clients = {}
    for ref in ("old", "legacy"):
        clients[ref] = own(store, ref)
        store.decision(Decision(id=clients[ref], run_id="r", symbol="BTC-USDT", proposed_action="BUY",
                                laya_label="CONTINUE", laya_confidence=1, llm_summary="s", evidence_ids=[],
                                risk_approved=True, risk_reasons=[], execution_status="VERIFIED",
                                source_mode="OKX_DEMO", intent_id=ref, quantity="0.0001",
                                limit_price="50100"))
    for _ in range(250):  # far beyond the old 200-decision window
        store.decision(Decision(run_id="r", symbol="BTC-USDT", proposed_action="NO_TRADE",
                                laya_label="REVIEW", laya_confidence=0, llm_summary="s", evidence_ids=[],
                                risk_approved=False, risk_reasons=["no_trade_proposed"],
                                execution_status="NOT_SENT", source_mode="OKX_DEMO", intent_id="n",
                                quantity="0"))
    store.record_fill("legacy", {"ord_id": "ord-legacy", "side": "buy", "avg_price": "1",
                                 "filled_qty": "0.0001", "fee": "0", "intent_id": "legacy",
                                 "decision_id": clients["legacy"], "source_mode": "OKX_DEMO"})
    seen = []

    async def reconcile(proposal, client_id, limit_price):
        seen.append(proposal.intent_id)
        agent.atk.last_fill = fill("buy", "0.0001", "50000", fee="-0.0000001", fee_ccy="BTC",
                                   ord_id="ord-" + proposal.intent_id)
        return "VERIFIED", "ord-" + proposal.intent_id, "filled"

    monkeypatch.setattr(agent.atk, "reconcile", reconcile)
    await agent._backfill_fills()
    assert sorted(seen) == ["legacy", "old"]
    assert store.fill_intents(schema=2) == {"old", "legacy"}
    seen.clear()
    await agent._backfill_fills()
    assert seen == []  # idempotent: nothing re-read once current
    await agent.close()


# --- pre-trade cost gate ---------------------------------------------------------------------


def config(**kw):
    values = dict(taker_fee_rate="0", fee_source="test", slippage_bps_per_leg="0", uncertainty_bps="0",
                  max_data_age_seconds=10, max_spread_bps="10", min_net_edge_bps="0")
    values.update(kw)
    return CostConfig(**values)


def assess(edge_bps="10", *, cfg=None, book=None, observation=None, action="BUY", validated=True,
           exit_horizon=900, age=0):
    now = utcnow()
    obs = observation or Observation(
        symbol="BTC-USDT", observed_at=now - timedelta(seconds=age), price="100", ask="100", bid="100",
        min_size="0.00001", lot_size="0.00000001", instrument_live=True,
    )
    edge = None if edge_bps is None else EdgeEstimate(
        expected_return_bps=edge_bps, uncertainty_bps="0", horizon_seconds=900, source="test",
        out_of_sample_validated=validated, sample_size=500, as_of=now,
    )
    proposal = Proposal(action=action, symbol="BTC-USDT", quantity="0.0001", intent_id="c", summary="s")
    return evaluate(obs, proposal, now=now, config=cfg or config(), edge=edge,
                    exit_plan=None if exit_horizon is None else ExitPlan(horizon_seconds=exit_horizon),
                    top_of_book=book if book is not None else {"bid_sz": "1", "ask_sz": "1"})


@pytest.mark.parametrize("threshold,approved", [("9.99", True), ("10", False), ("10.01", False)])
def test_edge_below_equal_above_cost_threshold(threshold, approved):
    out = assess("10", cfg=config(min_net_edge_bps=threshold))
    assert out.breakdown["expected_net_after_margin_bps"] == "10.00000000"
    assert out.approved is approved
    assert (out.status, out.reasons) == (("APPROVED", []) if approved else ("NO_TRADE", ["cost_insufficient_edge"]))


def test_positive_gross_edge_blocked_by_round_trip_fees_and_spread_not_double_counted():
    obs = Observation(symbol="BTC-USDT", observed_at=utcnow(), price="100", bid="99.99", ask="100.01",
                      min_size="0.00001", lot_size="0.00000001", instrument_live=True)
    out = assess("10", observation=obs, cfg=config(taker_fee_rate="0.001"))
    b = out.breakdown
    assert Decimal(b["expected_gross_edge"]) > 0 and "cost_insufficient_edge" in out.reasons
    assert b["entry_price"] == "100.01000000" and b["expected_exit_price"] == "100.09000000"
    # spread lives only in entry/exit prices; net = price result - both fees, nothing else
    assert Decimal(b["expected_net_after_costs"]) == (
        Decimal(b["price_result_after_spread_and_slippage"]) - Decimal(b["entry_fee"]) - Decimal(b["exit_fee"])
    )


def test_sell_round_trip_uses_bid_entry_and_ask_exit():
    obs = Observation(symbol="BTC-USDT", observed_at=utcnow(), price="100", bid="99.99", ask="100.01",
                      min_size="0.00001", lot_size="0.00000001", instrument_live=True)
    out = assess("50", observation=obs, action="SELL")
    assert out.breakdown["entry_price"] == "99.99000000" and out.approved


@pytest.mark.parametrize(
    "kwargs,reason,status",
    [
        (dict(age=30), "cost_stale_data", "NO_TRADE"),
        (dict(cfg=config(slippage_bps_per_leg="50")), "cost_insufficient_edge", "NO_TRADE"),
        (dict(book={"bid_sz": "1", "ask_sz": "0.00001"}), "cost_insufficient_liquidity", "NO_TRADE"),
        (dict(book={}), "cost_liquidity_unknown", "REVIEW"),
        (dict(cfg=config(taker_fee_rate=None)), "cost_unknown_fee", "REVIEW"),
        (dict(edge_bps=None), "cost_edge_source_missing", "REVIEW"),
        (dict(validated=False), "cost_edge_unverified", "REVIEW"),
        (dict(exit_horizon=None), "cost_exit_plan_missing", "REVIEW"),
        (dict(exit_horizon=60), "cost_exit_plan_missing", "REVIEW"),
    ],
)
def test_cost_gate_reason_codes(kwargs, reason, status):
    out = assess(**({"edge_bps": "100"} | kwargs))
    assert not out.approved and reason in out.reasons and out.status == status


def test_wide_spread_is_blocked():
    obs = Observation(symbol="BTC-USDT", observed_at=utcnow(), price="100", bid="99", ask="101",
                      min_size="0.00001", lot_size="0.00000001", instrument_live=True)
    assert "cost_excess_spread" in assess("1000", observation=obs).reasons


# --- agent integration -----------------------------------------------------------------------


def demo_agent(tmp_path, **kw):
    from aegis.agent import Agent

    return Agent(Settings(_env_file=None, source_mode="OKX_DEMO", db_path=tmp_path / "cg.sqlite3",
                          demo_enabled=True, demo_region_confirmed=True, okx_demo_api_key="test-demo",
                          okx_demo_secret_key="test-secret", okx_demo_passphrase="test-pass", **kw))


def install(agent, monkeypatch, calls):
    async def observe():
        obs = inputs()[0]
        obs.account_observed_at = obs.observed_at
        return obs

    async def classify(*a, **k):
        return inputs()[1]

    async def reason(*a, **k):
        return inputs()[2]

    async def place(*a):
        calls.append("place")
        return "venue"

    async def reconcile(*a):
        return "VERIFIED", "venue", "filled"

    for owner, name, fn in ((agent.atk, "observe", observe), (agent.models, "classify", classify),
                            (agent.models, "reason", reason), (agent.atk, "place", place),
                            (agent.atk, "reconcile", reconcile)):
        monkeypatch.setattr(owner, name, fn)


@pytest.mark.asyncio
async def test_demo_trade_without_measured_edge_is_never_sent(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from aegis.app import create_app

    agent, calls = demo_agent(tmp_path), []
    install(agent, monkeypatch, calls)
    decision = await agent.cycle()
    assert calls == [] and not decision.risk_approved and decision.execution_status == "NOT_SENT"
    assert {"cost_edge_source_missing", "cost_unknown_fee", "cost_exit_plan_missing"} <= set(decision.risk_reasons)
    gate = [e for e in agent.store.events(200) if e["type"] == "RISK_GATE"][-1]["details"]
    assert gate["cost_gate_enforced"] and gate["cost_assessment"]["status"] == "REVIEW"
    summary = agent.store.cost_summary()
    assert summary["blocked_when_enforced"] == 1 and summary["reason_counts"]["cost_edge_source_missing"] == 1
    await agent.close()

    app = create_app(Settings(_env_file=None, source_mode="MARKET_ONLY", db_path=tmp_path / "cg.sqlite3"))
    with TestClient(app) as api:
        assert api.get("/api/metrics/cost-gate").json()["blocked_when_enforced"] == 1


@pytest.mark.asyncio
async def test_measured_edge_admits_order_but_existing_limits_still_apply(tmp_path, monkeypatch):
    agent, calls = demo_agent(tmp_path), []
    install(agent, monkeypatch, calls)
    allow_costs(agent, monkeypatch)
    first = await agent.cycle()
    assert first.execution_status == "VERIFIED" and calls == ["place"]
    second = await agent.cycle()  # max_run_orders=1 is unchanged by the cost gate
    assert "run_budget_exhausted" in second.risk_reasons and calls == ["place"]
    await agent.close()


@pytest.mark.asyncio
async def test_mock_records_cost_assessment_without_enforcing(tmp_path):
    from aegis.agent import Agent

    agent = Agent(Settings(_env_file=None, source_mode="MOCK", db_path=tmp_path / "m.sqlite3"))
    decision = await agent.cycle("normal")
    assert decision.risk_approved and decision.venue_state == "MOCK_FILLED"
    summary = agent.store.cost_summary()
    assert summary["would_block_unenforced"] == 1 and summary["blocked_when_enforced"] == 0
    await agent.close()


def test_pnl_endpoint_serves_versioned_owned_fills_with_mark_source(tmp_path):
    from fastapi.testclient import TestClient

    from aegis.app import create_app

    path = tmp_path / "api.sqlite3"
    store = Store(path, [])
    client = own(store, "api")
    store.record_fill("api", fill("buy", "0.1", "40000", fee="-0.0001", fee_ccy="BTC",
                                  intent_id="api", decision_id=client, ord_id="ord-api"))
    store.save_mark(inputs()[0])
    store.close()
    with TestClient(create_app(Settings(_env_file=None, source_mode="MARKET_ONLY", db_path=path))) as api:
        assert api.get("/api/metrics").json()["pnl"] is None
        body = api.get("/api/metrics/pnl").json()
    assert body["schema_version"] == "aegis-demo-pnl-2" and body["net"] == "995.00000000"
    assert body["mark"]["source"].startswith("OKX ticker") and body["valuation_status"] == "CURRENT_MARK"
