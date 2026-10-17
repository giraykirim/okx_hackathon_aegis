import json

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
