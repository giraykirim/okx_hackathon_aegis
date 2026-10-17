import asyncio
from decimal import Decimal

import pytest
from test_policy import inputs

from aegis.settings import Settings


def runtime(tmp_path, **kwargs):
    from aegis.agent import Agent

    return Agent(Settings(source_mode="MOCK", db_path=tmp_path / "audit.sqlite3", **kwargs))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scenario,reason",
    [
        ("stale_feed", "stale_feed"),
        ("laya_halt", "laya_not_clear"),
        ("excess_exposure", "excess_exposure"),
        ("invalid_quantity", "invalid_quantity"),
        ("missing_approval", "approval_unavailable"),
        ("unknown_order", "unresolved_prior_order"),
    ],
)
async def test_unsafe_scenarios_never_execute(tmp_path, scenario, reason):
    agent = runtime(tmp_path)
    decision = await agent.cycle(scenario)
    assert not decision.risk_approved
    assert reason in decision.risk_reasons
    assert decision.execution_status == "NOT_SENT"
    assert agent.mock_execution_count == 0
    assert {e["type"] for e in agent.store.events()} >= {
        "OBSERVE",
        "CLASSIFY",
        "REASON",
        "RISK_GATE",
        "NO_TRADE",
        "VERIFY",
        "AUDIT",
    }
    await agent.close()


@pytest.mark.asyncio
async def test_stop_during_model_wait_prevents_new_submission(tmp_path, monkeypatch):
    from aegis.agent import Agent

    agent = Agent(
        Settings(
            source_mode="OKX_DEMO",
            db_path=tmp_path / "stop.sqlite3",
            demo_enabled=True,
            demo_region_confirmed=True,
            okx_demo_api_key="test-demo",
            okx_demo_secret_key="test-secret",
            okx_demo_passphrase="test-pass",
        )
    )
    entered = asyncio.Event()
    release = asyncio.Event()
    calls = []

    async def observe():
        obs = inputs()[0]
        obs.account_observed_at = obs.observed_at
        return obs

    async def classify(*args, **kwargs):
        return inputs()[1]

    async def reason(*args, **kwargs):
        entered.set()
        await release.wait()
        return inputs()[2]

    async def place(*args):
        calls.append("place")
        raise TimeoutError()

    async def reconcile(*args):
        raise TimeoutError()

    monkeypatch.setattr(agent.atk, "observe", observe)
    monkeypatch.setattr(agent.models, "classify", classify)
    monkeypatch.setattr(agent.models, "reason", reason)
    monkeypatch.setattr(agent.atk, "place", place)
    monkeypatch.setattr(agent.atk, "reconcile", reconcile)
    await agent.start()
    await entered.wait()
    stop_task = asyncio.create_task(agent.stop())
    await asyncio.sleep(0)
    release.set()
    await stop_task
    assert calls == []
    assert "approval_unavailable" in agent.store.decisions()[0]["risk_reasons"]
    await agent.close()


@pytest.mark.asyncio
async def test_mock_execution_cannot_be_exchange_verified(tmp_path):
    agent = runtime(tmp_path)
    decision = await agent.cycle("normal")
    assert decision.risk_approved
    assert agent.mock_execution_count == 1
    assert decision.execution_status == "NOT_SENT"
    assert decision.venue_order_id is None
    assert decision.venue_state == "MOCK_FILLED"
    assert decision.source_mode == "MOCK"
    assert agent.capabilities()["ATK_DEMO"]["status"] == "NOT_TESTED"
    await agent.close()


@pytest.mark.asyncio
async def test_duplicate_intent_is_vetoed(tmp_path):
    agent = runtime(tmp_path)
    await agent.cycle("duplicate_intent")
    second = await agent.cycle("duplicate_intent")
    assert not second.risk_approved
    assert "duplicate_intent" in second.risk_reasons
    assert agent.mock_execution_count == 1
    await agent.close()


@pytest.mark.asyncio
async def test_unresolved_order_survives_restart(tmp_path):
    agent = runtime(tmp_path)
    proposal = inputs()[2]
    assert agent.store.claim(proposal, "a" * 32, "OKX_DEMO")
    agent.store.order_status(proposal.intent_id, "UNKNOWN")
    await agent.close()
    restarted = runtime(tmp_path)
    decision = await restarted.cycle("normal")
    assert "unresolved_prior_order" in decision.risk_reasons
    assert restarted.mock_execution_count == 0
    await restarted.close()


def test_sqlite_claim_is_atomic_across_connections(tmp_path):
    from aegis.store import Store

    first = Store(tmp_path / "audit.sqlite3")
    second = Store(tmp_path / "audit.sqlite3")
    assert first.claim(inputs()[2], "a" * 32, "OKX_DEMO")
    assert not second.claim(inputs()[2], "b" * 32, "OKX_DEMO")
    other = inputs()[2].model_copy(update={"intent_id": "another"})
    assert not second.claim(other, "c" * 32, "OKX_DEMO")
    first.close()
    second.close()


@pytest.mark.asyncio
async def test_autonomous_start_is_idempotent_and_stop_joins_task(tmp_path):
    agent = runtime(tmp_path, cycle_seconds=1)
    await agent.start()
    task = agent.task
    await agent.start()
    assert agent.task is task
    for _ in range(100):
        if agent.store.decisions():
            break
        await asyncio.sleep(0.01)
    assert agent.store.decisions()
    await agent.stop()
    assert not agent.running
    assert task.done()
    await agent.close()


@pytest.mark.asyncio
async def test_market_observation_failure_still_audits_no_trade(tmp_path, monkeypatch):
    from aegis.agent import Agent

    agent = Agent(Settings(db_path=tmp_path / "audit.sqlite3"))

    async def fail():
        raise RuntimeError("sensitive provider error")

    monkeypatch.setattr(agent.atk, "observe", fail)
    decision = await agent.cycle()
    assert not decision.risk_approved and decision.execution_status == "NOT_SENT"
    assert "observation_unavailable" in decision.risk_reasons
    assert "sensitive provider error" not in str(agent.store.events())
    await agent.close()


@pytest.mark.asyncio
async def test_demo_timeout_is_unknown_and_next_cycle_only_reconciles(tmp_path, monkeypatch):
    from aegis.agent import Agent
    from aegis.models import Capability

    agent = Agent(
        Settings(
            source_mode="OKX_DEMO",
            db_path=tmp_path / "audit.sqlite3",
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
        return observation

    async def classify(*args, **kwargs):
        agent.models.capabilities["LAYA"] = Capability(status="PASS")
        return inputs()[1]

    async def reason(*args, **kwargs):
        agent.models.capabilities["EVREN"] = Capability(status="PASS")
        return inputs()[2]

    async def place(*args):
        calls.append("place")
        raise TimeoutError()

    async def reconcile(*args):
        calls.append("reconcile")
        raise TimeoutError()

    monkeypatch.setattr(agent.atk, "observe", observe)
    monkeypatch.setattr(agent.models, "classify", classify)
    monkeypatch.setattr(agent.models, "reason", reason)
    monkeypatch.setattr(agent.atk, "place", place)
    monkeypatch.setattr(agent.atk, "reconcile", reconcile)
    first = await agent.cycle()
    assert first.execution_status == "UNKNOWN"
    assert agent.store.unresolved()
    second = await agent.cycle()
    assert not second.risk_approved
    assert calls.count("place") == 1
    assert calls.count("reconcile") >= 1
    await agent.close()


@pytest.mark.asyncio
async def test_final_decision_and_intent_rollback_together_on_interruption(tmp_path):
    import sqlite3

    agent = runtime(tmp_path)
    decision = await agent.cycle("normal")
    agent.store.db.execute("""CREATE TRIGGER interrupt_decision BEFORE UPDATE ON decisions
        BEGIN SELECT RAISE(ABORT, 'simulated interruption'); END""")
    decision.execution_status = "VERIFIED"
    with pytest.raises(sqlite3.IntegrityError):
        agent.store.finalize(decision)
    row = agent.store.db.execute(
        "SELECT status FROM intents WHERE intent_id=?", (decision.intent_id,)
    ).fetchone()
    assert row["status"] == "NOT_SENT"
    assert agent.store.decisions()[0]["execution_status"] == "NOT_SENT"
    await agent.close()


@pytest.mark.asyncio
async def test_configured_mock_no_trade_and_halt_have_complete_normalized_timeline(tmp_path):
    agent = runtime(tmp_path, mock_autonomous_scenario="no_trade")
    await agent.start()
    for _ in range(100):
        if agent.store.decisions():
            break
        await asyncio.sleep(0.01)
    await agent.stop()
    decision = agent.store.decisions()[0]
    assert decision["proposed_action"] == "NO_TRADE" and decision["execution_status"] == "NOT_SENT"
    phases = [e["details"].get("phase") for e in agent.store.events()]
    assert [p for p in phases if p] == [
        "OBSERVE",
        "CLASSIFY",
        "REASON",
        "RISK_CHECK",
        "NO_TRADE",
        "VERIFY",
        "AUDIT",
    ]
    assert agent.mock_execution_count == 0
    stopped_event_count = len(agent.store.events())
    await agent.stop()
    assert len(agent.store.events()) == stopped_event_count
    halt = await agent.cycle("laya_halt")
    assert halt.laya_label == "HALT" and not halt.risk_approved
    await agent.close()


@pytest.mark.asyncio
async def test_cycle_deadline_audits_and_stops_without_execution(tmp_path, monkeypatch):
    from aegis.agent import Agent

    agent = Agent(Settings(_env_file=None, db_path=tmp_path / "deadline.sqlite3", cycle_timeout_seconds=0.02))

    async def slow():
        await asyncio.sleep(0.1)
        return inputs()[0]

    monkeypatch.setattr(agent.atk, "observe", slow)
    decision = await agent.cycle()
    assert decision.execution_status == "NOT_SENT" and "cycle_timeout" in decision.risk_reasons
    assert not agent.running and agent.stop_requested
    assert agent.store.events()[-1]["type"] == "AUDIT"
    await agent.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("label,submitted", [("REVIEW", True), ("HALT", False)])
async def test_demo_sell_executes_with_abstaining_laya_and_loaded_account(
    tmp_path, monkeypatch, label, submitted
):
    from aegis.agent import Agent
    from aegis.models import Classification

    agent = Agent(
        Settings(
            source_mode="OKX_DEMO",
            db_path=tmp_path / "demo-sell.sqlite3",
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
        observation.exposure_quote = Decimal("99549.3")
        observation.base_available = Decimal("1")
        return observation

    async def classify(*args, **kwargs):
        return Classification(
            label=label, confidence=0, abstained=label == "REVIEW", model_version="base", latency_ms=1
        )

    async def reason(*args, **kwargs):
        return inputs()[2].model_copy(update={"action": "SELL"})

    async def place(*args):
        calls.append("place")
        return "venue-1"

    async def reconcile(*args):
        return "VERIFIED", "venue-1", "filled"

    monkeypatch.setattr(agent.atk, "observe", observe)
    monkeypatch.setattr(agent.models, "classify", classify)
    monkeypatch.setattr(agent.models, "reason", reason)
    monkeypatch.setattr(agent.atk, "place", place)
    monkeypatch.setattr(agent.atk, "reconcile", reconcile)
    decision = await agent.cycle()
    assert (calls == ["place"]) is submitted
    assert decision.risk_approved is submitted
    assert decision.execution_status == ("VERIFIED" if submitted else "NOT_SENT")
    await agent.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("rejected,expected", [(True, "FAILED"), (False, "UNKNOWN")])
async def test_not_found_after_submit_resolves_only_when_venue_rejected(
    tmp_path, monkeypatch, rejected, expected
):
    from aegis.agent import Agent
    from aegis.atk import ATKCommandError
    from aegis.models import Classification

    agent = Agent(
        Settings(
            source_mode="OKX_DEMO",
            db_path=tmp_path / "rejected.sqlite3",
            demo_enabled=True,
            demo_region_confirmed=True,
            okx_demo_api_key="test-demo",
            okx_demo_secret_key="test-secret",
            okx_demo_passphrase="test-pass",
        )
    )

    async def observe():
        observation = inputs()[0]
        observation.account_observed_at = observation.observed_at
        return observation

    async def classify(*args, **kwargs):
        return Classification(label="REVIEW", confidence=0, abstained=True, model_version="b", latency_ms=1)

    async def reason(*args, **kwargs):
        return inputs()[2]

    async def place(*args):
        raise ATKCommandError("51008", "Insufficient balance") if rejected else TimeoutError()

    async def call(operation, *args):
        assert operation == "get"
        raise ATKCommandError("51603", "Order does not exist")

    monkeypatch.setattr(agent.atk, "observe", observe)
    monkeypatch.setattr(agent.models, "classify", classify)
    monkeypatch.setattr(agent.models, "reason", reason)
    monkeypatch.setattr(agent.atk, "place", place)
    monkeypatch.setattr(agent.atk, "call", call)
    decision = await agent.cycle()
    assert decision.execution_status == expected
    assert bool(agent.store.unresolved()) is (expected == "UNKNOWN")
    if rejected:
        execute = [e for e in agent.store.events(100) if e["type"] == "EXECUTE"][-1]
        assert execute["details"]["error_code"] == "51008"
    await agent.close()


def test_venue_rejected_claim_releases_run_budget(tmp_path):
    from aegis.store import Store

    store = Store(tmp_path / "budget.sqlite3", [])
    proposal = inputs()[2]
    assert store.claim(proposal, "a" * 32, "OKX_DEMO", run_id="r", reserved_notional=Decimal("8"))
    assert store.run_budget("r") == (1, Decimal("8"))
    store.order_status(proposal.intent_id, "FAILED", None, "not_found")
    assert store.run_budget("r") == (0, Decimal("0"))
    store.close()


@pytest.mark.asyncio
async def test_laya_receives_complete_post_proposal_operational_context(tmp_path, monkeypatch):
    from aegis.agent import Agent
    from aegis.models import Capability, Classification

    agent = Agent(
        Settings(
            source_mode="OKX_DEMO",
            db_path=tmp_path / "context.sqlite3",
            demo_enabled=True,
            demo_region_confirmed=True,
            okx_demo_api_key="test-demo",
            okx_demo_secret_key="test-secret",
            okx_demo_passphrase="test-pass",
            laya_expected_version="base",
        )
    )
    seen = {}

    async def observe():
        observation = inputs()[0]
        observation.account_observed_at = observation.observed_at
        agent.atk.capabilities["ATK_ACCOUNT"] = Capability(status="PASS")
        return observation

    async def reason(*args, **kwargs):
        agent.models.capabilities["EVREN"] = Capability(status="PASS")
        return inputs()[2]

    async def classify(*args, context=None):
        seen["context"] = context
        return Classification(
            label="HALT", confidence=0.9, abstained=False, model_version="base", latency_ms=1
        )

    monkeypatch.setattr(agent.atk, "observe", observe)
    monkeypatch.setattr(agent.models, "reason", reason)
    monkeypatch.setattr(agent.models, "classify", classify)
    decision = await agent.cycle()
    facts = seen["context"]["operational"]
    assert None not in facts.values()
    assert facts["intent_requested"] is True and facts["approval_available"] is True
    assert not {"quote_available", "base_available", "exposure_quote", "intent_id"} & facts.keys()
    # An explicit LAYA HALT from the full-context call still vetoes the order.
    assert not decision.risk_approved and "laya_not_clear" in decision.risk_reasons
    await agent.close()


@pytest.mark.asyncio
async def test_evren_receives_atk_trend_features(tmp_path, monkeypatch):
    from aegis.agent import Agent

    agent = Agent(Settings(source_mode="MARKET_ONLY", db_path=tmp_path / "trend.sqlite3"))
    seen = {}
    features = {"bar": "15m", "sma_8_vs_32_pct": "0.120", "return_1h_pct": "0.050"}

    async def observe():
        return inputs()[0]

    async def trend():
        return features

    async def reason(*args, market_features=None, **kwargs):
        seen["features"] = market_features
        return inputs()[2]

    async def classify(*args, **kwargs):
        return inputs()[1]

    monkeypatch.setattr(agent.atk, "observe", observe)
    monkeypatch.setattr(agent.atk, "trend", trend)
    monkeypatch.setattr(agent.models, "reason", reason)
    monkeypatch.setattr(agent.models, "classify", classify)
    await agent.cycle()
    assert seen["features"] == features
    assert any(
        e["details"].get("market_features") == features
        for e in agent.store.events(100)
        if e["type"] == "OBSERVE"
    )
    await agent.close()


@pytest.mark.asyncio
async def test_one_trade_per_closed_candle(tmp_path, monkeypatch):
    from aegis.agent import Agent

    agent = Agent(
        Settings(
            source_mode="OKX_DEMO",
            db_path=tmp_path / "candle.sqlite3",
            demo_enabled=True,
            demo_region_confirmed=True,
            okx_demo_api_key="test-demo",
            okx_demo_secret_key="test-secret",
            okx_demo_passphrase="test-pass",
            max_run_orders=10,
        )
    )
    calls = []

    async def observe():
        observation = inputs()[0]
        observation.account_observed_at = observation.observed_at
        return observation

    async def trend():
        return {"candle_open_ts": "1792251000000"}

    async def reason(*args, **kwargs):
        return inputs()[2]

    async def classify(*args, **kwargs):
        return inputs()[1]

    async def place(*args):
        calls.append("place")
        return "venue"

    async def reconcile(*args):
        return "VERIFIED", "venue", "filled"

    for name, fn in (("observe", observe), ("trend", trend), ("place", place), ("reconcile", reconcile)):
        monkeypatch.setattr(agent.atk, name, fn)
    monkeypatch.setattr(agent.models, "reason", reason)
    monkeypatch.setattr(agent.models, "classify", classify)
    first, second = await agent.cycle(), await agent.cycle()
    assert first.execution_status == "VERIFIED" and calls == ["place"]
    assert second.proposed_action == "NO_TRADE" and "same" not in second.llm_summary.lower()
    await agent.close()
