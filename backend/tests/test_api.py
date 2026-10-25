import json

import pytest
from fastapi.testclient import TestClient

from aegis.settings import Settings

TOKEN = "local-test-control-token-32-characters"


def client(tmp_path, **kwargs):
    from aegis.app import create_app

    settings = dict(source_mode="MOCK", db_path=tmp_path / "api.sqlite3", control_token=TOKEN)
    settings.update(kwargs)
    return TestClient(create_app(Settings(**settings)))


def headers():
    return {"Authorization": "Bearer " + TOKEN}


def test_all_read_contract_routes_and_empty_state(tmp_path):
    with client(tmp_path) as api:
        for route in (
            "health",
            "snapshot",
            "events",
            "decisions",
            "metrics",
            "web3/identity",
            "capabilities",
        ):
            response = api.get("/api/" + route)
            assert response.status_code == 200, response.text
        assert api.get("/api/events").json() == []
        assert api.get("/api/metrics").json()["pnl"] is None
        assert api.get("/api/metrics/pnl").json() is None
        identity = api.get("/api/web3/identity").json()
        assert identity["verified"] is False and identity["chain_id"] == 43113
        assert identity["agent_id"] is None and identity["verification_status"] == "NOT_TESTED"


def test_controls_require_authentication(tmp_path):
    with client(tmp_path) as api:
        for route in ("agent/start", "agent/stop", "demo/scenario"):
            response = api.post("/api/" + route, json={"scenario": "normal"})
            assert response.status_code == 401
        assert api.post("/api/agent/start", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_missing_control_token_disables_mutations(tmp_path):
    with client(tmp_path, control_token=None) as api:
        assert api.post("/api/agent/start", headers=headers()).status_code == 503


def test_mock_scenario_and_persisted_timeline(tmp_path):
    with client(tmp_path) as api:
        response = api.post("/api/demo/scenario", headers=headers(), json={"scenario": "stale_feed"})
        assert response.status_code == 200
        decision = response.json()
        assert "stale_feed" in decision["risk_reasons"]
        assert not decision["risk_approved"]
        assert api.get("/api/decisions").json()[0]["id"] == decision["id"]
        assert api.get("/api/snapshot").json()["latest_decision"]["id"] == decision["id"]
        assert len(api.get("/api/events").json()) >= 6
    with client(tmp_path) as restarted:
        assert restarted.get("/api/decisions").json()[0]["id"] == decision["id"]


def test_scenarios_forbidden_outside_mock(tmp_path):
    with client(tmp_path, source_mode="MARKET_ONLY") as api:
        assert (
            api.post("/api/demo/scenario", headers=headers(), json={"scenario": "normal"}).status_code == 409
        )


def test_limits_extra_fields_unknown_scenarios_and_injection_are_rejected(tmp_path):
    with client(tmp_path) as api:
        for url in ("/api/events?limit=0", "/api/events?limit=1001", "/api/decisions?limit=-1"):
            assert api.get(url).status_code == 422
        assert (
            api.post("/api/demo/scenario", headers=headers(), json={"scenario": "withdraw"}).status_code
            == 422
        )
        assert (
            api.post(
                "/api/demo/scenario", headers=headers(), json={"scenario": "normal", "live": True}
            ).status_code
            == 422
        )


def test_start_stop_and_schema_security(tmp_path):
    with client(tmp_path) as api:
        assert api.post("/api/agent/start", headers=headers()).json()["running"] is True
        assert api.post("/api/agent/stop", headers=headers()).json()["running"] is False
        schema = api.get("/openapi.json").json()
        assert set(schema["paths"]) == {
            "/api/" + path
            for path in (
                "health",
                "snapshot",
                "events",
                "decisions",
                "metrics",
                "metrics/pnl",
                "metrics/cost-gate",
                "metrics/exit-shadow",
                "stream",
                "agent/start",
                "agent/stop",
                "demo/scenario",
                "web3/identity",
                "capabilities",
                "v1/risk/evaluate",
                "v1/service",
            )
        }
        assert schema["paths"]["/api/agent/start"]["post"]["security"] == [{"HTTPBearer": []}]
        assert "text/event-stream" in schema["paths"]["/api/stream"]["get"]["responses"]["200"]["content"]


def test_secret_redaction_and_sse_cursor(tmp_path):
    from aegis.models import Event

    with client(tmp_path) as api:
        store = api.app.state.agent.store
        first = Event(
            run_id="run",
            type="TEST",
            severity="INFO",
            actor="test",
            message="test",
            source_mode="MOCK",
            details={"api_key": "hidden", "nested": {"value": TOKEN}},
        )
        store.event(first)
        second = Event(
            run_id="run",
            type="TEST",
            severity="INFO",
            actor="test",
            message="evren_llm_hidden",
            source_mode="MOCK",
        )
        store.event(second)
        data = api.get("/api/events").json()
        assert TOKEN not in json.dumps(data)
        assert "hidden" not in json.dumps(data)
        assert [e["id"] for e in store.events(after=first.id)] == [second.id]


@pytest.mark.parametrize("mode,started", [("MARKET_ONLY", True), ("OKX_DEMO", False)])
def test_autostart_only_for_non_executing_modes(tmp_path, monkeypatch, mode, started):
    from fastapi.testclient import TestClient

    from aegis.agent import Agent
    from aegis.app import create_app
    from aegis.settings import Settings

    calls = []

    async def start(self):
        calls.append(True)

    monkeypatch.setattr(Agent, "start", start)
    app = create_app(Settings(_env_file=None, db_path=tmp_path / "auto.sqlite3", source_mode=mode, autostart=True))
    with TestClient(app):
        pass
    assert bool(calls) is started


def test_demo_pnl_is_derived_from_recorded_venue_fills(tmp_path):
    from decimal import Decimal

    from aegis.models import Proposal
    from test_policy import inputs

    with client(tmp_path) as api:
        store = api.app.state.agent.store
        # Only fills of the agent's own journaled demo intents are counted.
        for ref in ("intent-buy", "intent-sell"):
            proposal = Proposal(action="BUY", symbol="BTC-USDT", quantity="0.1", intent_id=ref, summary="t")
            assert store.claim(proposal, "client-" + ref, "OKX_DEMO")
            store.order_status(ref, "VERIFIED", "ord-" + ref, "filled")
        store.record_fill(
            "intent-buy",
            {
                "ord_id": "ord-intent-buy",
                "decision_id": "client-intent-buy",
                "intent_id": "intent-buy",
                "side": "buy",
                "avg_price": "40000",
                "filled_qty": "0.1",
                "fee": "-2",  # OKX: negative = fee charged
                "fee_ccy": "USDT",
                "filled_at": "2026-10-21T10:00:00+00:00",
                "source_mode": "OKX_DEMO",
            },
        )
        store.record_fill(
            "intent-sell",
            {
                "ord_id": "ord-intent-sell",
                "decision_id": "client-intent-sell",
                "intent_id": "intent-sell",
                "side": "sell",
                "avg_price": "44000",
                "filled_qty": "0.05",
                "fee": "-1",
                "fee_ccy": "USDT",
                "filled_at": "2026-10-21T10:05:00+00:00",
                "source_mode": "OKX_DEMO",
            },
        )
        # Non-demo fills must never contribute to demo PnL.
        store.record_fill(
            "intent-mock",
            {
                "intent_id": "intent-mock",
                "side": "buy",
                "avg_price": "1",
                "filled_qty": "1000",
                "fee": "0",
                "fee_ccy": "USDT",
                "filled_at": "2026-10-21T10:10:00+00:00",
                "source_mode": "MOCK",
            },
        )

        # Without a recorded venue ticker the open inventory cannot be valued.
        unvalued = api.get("/api/metrics/pnl").json()
        assert unvalued["fill_count"] == 2 and unvalued["realized"] == "198.00000000"
        assert unvalued["unrealized"] is None and unvalued["net"] is None
        assert unvalued["valuation_status"] == "NO_MARK"

        observation = inputs()[0].model_copy(update={"price": Decimal("46000")})
        store.save_mark(observation)
        pnl = store.demo_pnl(now=observation.observed_at)
        assert pnl["fill_count"] == 2
        assert pnl["realized"] == "198.00000000"
        assert pnl["unrealized"] == "299.00000000"
        assert pnl["fees"] == "3.00000000"
        assert pnl["net"] == "497.00000000"
        assert pnl["inventory_qty"] == "0.05000000"
        assert pnl["average_cost"] == "40020.00000000"
        assert pnl["mark_price"] == "46000.00000000"

        assert api.get("/api/metrics").json()["pnl"] is None
        demo = api.get("/api/metrics/pnl").json()
        # The persisted mark survives without any in-memory observation.
        assert demo["net"] == "497.00000000" and demo["mark"]["price"] == "46000"
