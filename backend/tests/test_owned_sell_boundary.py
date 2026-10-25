"""Real Agent.cycle boundary: an OKX_DEMO SELL is limited to the agent's own net inventory."""

from decimal import Decimal

import pytest
from test_policy import allow_costs, inputs
from test_position_lifecycle import fill

from aegis.settings import Settings

OWNED_REASONS = {"owned_inventory_unavailable", "insufficient_owned_inventory"}


def ledger(inventory, *, complete=True, valuation="OK"):
    return {
        "complete": complete,
        "inventory_qty": inventory,
        "issues": [],
        "valuation_status": valuation,
        "excluded_unowned_fills": 0,
    }


def returns(value):
    def demo_pnl(*args, **kwargs):
        return value

    return demo_pnl


def demo_agent(tmp_path, monkeypatch, *, action="SELL", base="1", quantity="0.0001", pnl=None):
    from aegis.agent import Agent

    agent = Agent(
        Settings(
            source_mode="OKX_DEMO",
            db_path=tmp_path / "owned.sqlite3",
            demo_enabled=True,
            demo_region_confirmed=True,
            okx_demo_api_key="test-demo",
            okx_demo_secret_key="test-secret",
            okx_demo_passphrase="test-pass",
        )
    )
    calls = []

    async def observe():
        observation = inputs()[0]
        observation.account_observed_at = observation.observed_at
        observation.base_available = Decimal(base)
        return observation

    async def trend():
        return {"bar": "15m"}

    async def reason(*args, **kwargs):
        return inputs()[2].model_copy(update={"action": action, "quantity": Decimal(quantity)})

    async def classify(*args, **kwargs):
        return inputs()[1]

    async def place(*args):
        calls.append("place")
        return "venue-1"

    async def reconcile(*args):
        return "VERIFIED", "venue-1", "filled"

    for name, fn in (("observe", observe), ("trend", trend), ("place", place), ("reconcile", reconcile)):
        monkeypatch.setattr(agent.atk, name, fn)
    monkeypatch.setattr(agent.models, "reason", reason)
    monkeypatch.setattr(agent.models, "classify", classify)
    if pnl is not None:
        monkeypatch.setattr(agent.store, "demo_pnl", pnl)
    allow_costs(agent, monkeypatch)
    return agent, calls


def assert_vetoed(agent, decision, calls, reason):
    assert not decision.risk_approved
    assert decision.execution_status == "NOT_SENT"
    assert reason in decision.risk_reasons
    assert calls == []
    assert any(
        reason in e["details"].get("reasons", []) for e in agent.store.events(200) if e["type"] == "RISK_GATE"
    )


def seed_owned_fill(agent, ref, side, qty, fee="0", ccy="BTC", t=0):
    """Use the existing schema-2 fixture and real intent/client/venue ownership checks."""
    proposal = inputs()[2].model_copy(
        update={"action": side.upper(), "quantity": Decimal(qty), "intent_id": ref}
    )
    client = ("owned-" + ref).ljust(32, "0")[:32]
    assert agent.store.claim(proposal, client, "OKX_DEMO")
    agent.store.order_status(ref, "VERIFIED", "ord-" + ref, "filled")
    agent.store.record_fill(ref, fill(ref, client, side, qty, "50000", fee, ccy, t))
    owned, excluded = agent.store.owned_demo_fills()
    assert excluded == 0 and any(row["intent_id"] == ref for row in owned)


@pytest.mark.asyncio
async def test_foreign_account_btc_cannot_be_sold(tmp_path, monkeypatch):
    agent, calls = demo_agent(tmp_path, monkeypatch, base="1")
    decision = await agent.cycle()
    assert not decision.risk_approved and decision.execution_status == "NOT_SENT"
    # Every other gate passes; only the missing agent ownership vetoes.
    assert decision.risk_reasons and set(decision.risk_reasons) <= OWNED_REASONS
    assert calls == []
    await agent.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("valuation", ["OK", "NO_MARK", "STALE_MARK"])
async def test_sell_equal_to_owned_inventory_reaches_place(tmp_path, monkeypatch, valuation):
    owned = str(inputs()[2].quantity)
    agent, calls = demo_agent(tmp_path, monkeypatch, pnl=returns(ledger(owned, valuation=valuation)))
    decision = await agent.cycle()
    assert decision.risk_approved and calls == ["place"]
    assert decision.execution_status == "VERIFIED"
    await agent.close()


@pytest.mark.asyncio
async def test_sell_above_owned_inventory_is_vetoed(tmp_path, monkeypatch):
    observation, _, proposal, _ = inputs()
    owned = str(proposal.quantity - observation.lot_size)
    agent, calls = demo_agent(tmp_path, monkeypatch, pnl=returns(ledger(owned)))
    decision = await agent.cycle()
    assert_vetoed(agent, decision, calls, "insufficient_owned_inventory")
    await agent.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "result",
    [
        None,
        {},
        {"complete": True},
        ledger("1", complete=False),
        ledger("1", complete=None),
        ledger("1", complete="True"),
        ledger("1", complete=1),
        ledger("1", complete=False, valuation="NO_MARK"),
        {**ledger("1"), "issues": ["missing_fee:bad"]},
        {**ledger("1", complete=False, valuation="NO_MARK"), "issues": ["mark_price_missing", "missing_fee:bad"]},
        ledger(None),
        ledger(1),
        ledger("not-a-number"),
        ledger("NaN"),
        ledger("Infinity"),
        ledger("-Infinity"),
        ledger("-0.00000001"),
    ],
)
async def test_unknown_or_corrupt_ownership_is_vetoed(tmp_path, monkeypatch, result):
    agent, calls = demo_agent(tmp_path, monkeypatch, pnl=returns(result))
    decision = await agent.cycle()
    assert_vetoed(agent, decision, calls, "owned_inventory_unavailable")
    await agent.close()


@pytest.mark.asyncio
async def test_ownership_read_error_is_vetoed(tmp_path, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("ledger unreadable")

    agent, calls = demo_agent(tmp_path, monkeypatch, pnl=broken)
    decision = await agent.cycle()
    assert_vetoed(agent, decision, calls, "owned_inventory_unavailable")
    await agent.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["PENDING", "UNKNOWN"])
async def test_unresolved_order_still_vetoes_with_sufficient_ownership(tmp_path, monkeypatch, status):
    agent, calls = demo_agent(tmp_path, monkeypatch)
    seed_owned_fill(agent, "buy-before-pending", "buy", "0.0002")
    prior = inputs()[2]
    assert agent.store.claim(prior, "a" * 32, "OKX_DEMO")
    agent.store.order_status(prior.intent_id, status)
    decision = await agent.cycle()
    assert_vetoed(agent, decision, calls, "unresolved_prior_order")
    await agent.close()


@pytest.mark.asyncio
async def test_account_available_limit_remains_with_sufficient_ownership(tmp_path, monkeypatch):
    observation, _, proposal, _ = inputs()
    base = str(proposal.quantity - observation.lot_size)
    agent, calls = demo_agent(tmp_path, monkeypatch, base=base, pnl=returns(ledger("1")))
    decision = await agent.cycle()
    assert_vetoed(agent, decision, calls, "insufficient_base")
    assert not OWNED_REASONS & set(decision.risk_reasons)
    await agent.close()


@pytest.mark.asyncio
async def test_demo_buy_does_not_consult_owned_inventory(tmp_path, monkeypatch):
    def unread(*args, **kwargs):
        raise AssertionError("BUY must not depend on the sell ownership ledger")

    agent, calls = demo_agent(tmp_path, monkeypatch, action="BUY", pnl=unread)
    decision = await agent.cycle()
    assert decision.risk_approved and calls == ["place"]
    await agent.close()


@pytest.mark.asyncio
async def test_mock_sell_keeps_simulation_semantics_without_ownership(tmp_path, monkeypatch):
    from aegis.agent import Agent

    agent = Agent(Settings(source_mode="MOCK", db_path=tmp_path / "mock.sqlite3"))
    original = agent.mock_inputs

    def mock_inputs(scenario):
        observation, laya, proposal = original(scenario)
        return observation, laya, proposal.model_copy(update={"action": "SELL"})

    def unread(*args, **kwargs):
        raise AssertionError("MOCK must not consult the demo ledger")

    monkeypatch.setattr(agent, "mock_inputs", mock_inputs)
    monkeypatch.setattr(agent.store, "demo_pnl", unread)
    decision = await agent.cycle("normal")
    assert decision.proposed_action == "SELL" and decision.risk_approved
    assert agent.mock_execution_count == 1
    assert decision.execution_status == "NOT_SENT" and decision.venue_state == "MOCK_FILLED"
    await agent.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("quantity,approved", [("0.0001998", True), ("0.0002", False)])
async def test_real_buy_btc_fee_bounds_the_actual_sell_path(tmp_path, monkeypatch, quantity, approved):
    agent, calls = demo_agent(tmp_path, monkeypatch, quantity=quantity)
    try:
        seed_owned_fill(agent, "buy-with-btc-fee", "buy", "0.0002", "-0.0000002")
        pnl = agent.store.demo_pnl()
        assert pnl["complete"] is False and pnl["inventory_qty"] == "0.00019980"
        assert pnl["valuation_status"] == "NO_MARK"
        assert pnl["issues"] == ["mark_price_missing"]
        proposal = inputs()[2].model_copy(update={"action": "SELL", "quantity": Decimal(quantity)})
        assert agent.owned_sell_reasons(proposal) == ([] if approved else ["insufficient_owned_inventory"])
        decision = await agent.cycle()
        if approved:
            assert decision.risk_approved and calls == ["place"]
            assert decision.execution_status == "VERIFIED"
        else:
            assert_vetoed(agent, decision, calls, "insufficient_owned_inventory")
            assert decision.risk_reasons == ["insufficient_owned_inventory"]
    finally:
        await agent.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("quantity,approved", [("0.0000999", True), ("0.0001", False)])
async def test_real_prior_sell_reduces_the_next_sell_authority(tmp_path, monkeypatch, quantity, approved):
    agent, calls = demo_agent(tmp_path, monkeypatch, quantity=quantity)
    try:
        seed_owned_fill(agent, "buy-before-partial", "buy", "0.0002", "-0.0000002")
        seed_owned_fill(agent, "partial-sell", "sell", "0.0000999", "-0.004995", "USDT", 10)
        pnl = agent.store.demo_pnl()
        assert pnl["complete"] is False and pnl["inventory_qty"] == "0.00009990"
        assert pnl["fill_count"] == 2
        decision = await agent.cycle()
        if approved:
            assert decision.risk_approved and calls == ["place"]
            assert decision.execution_status == "VERIFIED"
        else:
            assert_vetoed(agent, decision, calls, "insufficient_owned_inventory")
            assert decision.risk_reasons == ["insufficient_owned_inventory"]
    finally:
        await agent.close()
