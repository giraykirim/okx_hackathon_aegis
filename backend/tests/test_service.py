import asyncio
import hashlib
import json
from datetime import timedelta

import pytest
import yaml
from fastapi.testclient import TestClient
from test_policy import inputs

from aegis.app import create_app
from aegis.models import utcnow
from aegis.settings import ROOT, Settings

SERVICE_KEY = "test-service-credential-separate-from-control"
CONTROL_KEY = "test-admin-control-not-a-service-credential"
FROZEN_V2_SHA256 = "a437caaa81ae590fc258aa0aeeb6498b1c38ec745483a701a4b2f0c66314d5ae"


def client(tmp_path, **kwargs):
    return TestClient(
        create_app(
            Settings(
                _env_file=None,
                db_path=tmp_path / "service.sqlite3",
                control_token=CONTROL_KEY,
                service_api_key=kwargs.pop("service_api_key", SERVICE_KEY),
                **kwargs,
            )
        )
    )


def headers():
    return {"X-AEGIS-Key": SERVICE_KEY}


def intent(**kwargs):
    return {"symbol": "BTC-USDT", "action": "BUY", "quantity": "0.0001", **kwargs}


def prepare(api, monkeypatch, *, observation=None):
    service = api.app.state.risk_service
    calls = []

    async def observe(*args, **kwargs):
        calls.append("observe")
        return observation or inputs()[0]

    async def forbidden(*args, **kwargs):
        raise AssertionError("A risk assessment must not access execution")

    monkeypatch.setattr(service.atk, "observe", observe)
    monkeypatch.setattr(service.atk, "place", forbidden)
    monkeypatch.setattr(service.atk, "reconcile", forbidden)
    monkeypatch.setattr(api.app.state.agent.atk, "place", forbidden)
    return service, calls


def test_frozen_v2_contract_is_unchanged_and_paths_components_still_match():
    path = ROOT.parent / "contracts/openapi.yaml"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == FROZEN_V2_SHA256
    frozen = yaml.safe_load(path.read_text())
    current = create_app().openapi()
    for name, value in frozen["paths"].items():
        assert current["paths"][name] == value
    for kind, definitions in frozen["components"].items():
        for name, value in definitions.items():
            assert current["components"][kind][name] == value


def test_public_service_metadata_is_honest_and_has_no_secrets(tmp_path):
    with client(tmp_path) as api:
        response = api.get("/api/v1/service")
        assert response.status_code == 200
        data = response.json()
        assert data["execution_authority"] is False
        assert data["okx_ai"]["listing_status"] == "NOT_LISTED"
        assert data["okx_ai"]["integration_feasibility"] == "POSSIBLE"
        assert data["public_url"] is None
        assert data["pricing"]["status"] == "PROPOSED_NOT_BILLED"
        assert data["auth"]["header"] == "X-AEGIS-Key"
        assert SERVICE_KEY not in response.text and CONTROL_KEY not in response.text


def test_assessment_auth_is_separate_from_controls(tmp_path):
    with client(tmp_path) as api:
        for supplied in (
            {},
            {"X-AEGIS-Key": "wrong"},
            {"X-AEGIS-Key": CONTROL_KEY},
            {"Authorization": "Bearer " + CONTROL_KEY},
        ):
            assert api.post("/api/v1/risk/evaluate", json=intent(), headers=supplied).status_code == 401
        assert (
            api.post("/api/agent/start", headers={"Authorization": "Bearer " + SERVICE_KEY}).status_code
            == 401
        )
    with client(tmp_path, service_api_key=None) as api:
        assert api.post("/api/v1/risk/evaluate", json=intent(), headers=headers()).status_code == 503


@pytest.mark.parametrize(
    "extra",
    [
        {"account_known": True},
        {"quote_available": "1000000"},
        {"source_mode": "MOCK"},
        {"market_fresh": True},
        {"approval_available": True},
        {"laya_label": "CONTINUE"},
        {"market_url": "http://untrusted.invalid"},
        {"execute": True},
    ],
)
def test_caller_cannot_supply_trusted_flags_or_tools(tmp_path, extra):
    with client(tmp_path) as api:
        response = api.post("/api/v1/risk/evaluate", json=intent(**extra), headers=headers())
        assert response.status_code == 422


def test_assessment_sources_market_but_never_borrows_account_or_trades(tmp_path, monkeypatch):
    with client(tmp_path, source_mode="MOCK") as api:
        service, calls = prepare(api, monkeypatch)
        assert service.atk.settings.source_mode == "MARKET_ONLY"
        assert not service.atk.settings.demo_ready()
        response = api.post("/api/v1/risk/evaluate", json=intent(), headers=headers())
        assert response.status_code == 200, response.text
        data = response.json()
        assert calls == ["observe"]
        assert data["source_mode"] == "MARKET_ONLY"
        assert data["execution_authority"] is False and data["order_permission"] is False
        assert data["account_provenance"] == "UNAVAILABLE"
        assert data["assessment"] == "REVIEW"
        assert "unknown_account" in data["reasons"]
        assert not {"insufficient_quote", "insufficient_base", "excess_exposure"} & set(data["reasons"])
        assert data["laya_status"] == "UNAVAILABLE"
        assert data["evren_status"] == "FALLBACK"
        assert data["market_checks"]["status"] == "PASS"
        assert api.get("/api/decisions").json() == []
        assert api.app.state.agent.store.db.execute("SELECT count(*) FROM intents").fetchone()[0] == 0
        assert api.get("/api/events").json()[-1]["type"] == "SERVICE_ASSESSMENT"
        digest = data.pop("assessment_sha256")
        assert (
            digest
            == hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        )


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"observed_at": utcnow() - timedelta(minutes=1)}, "stale_feed"),
        ({"instrument_live": False}, "instrument_unavailable"),
    ],
)
def test_unsafe_server_market_is_halt(tmp_path, monkeypatch, change, reason):
    obs = inputs()[0].model_copy(update=change)
    with client(tmp_path) as api:
        prepare(api, monkeypatch, observation=obs)
        response = api.post("/api/v1/risk/evaluate", json=intent(), headers=headers())
        data = response.json()
        assert data["assessment"] == "HALT"
        assert reason in data["reasons"]
        assert data["market_checks"]["status"] == "FAIL"


def test_excess_order_is_halt_with_no_side_effect(tmp_path, monkeypatch):
    with client(tmp_path) as api:
        prepare(api, monkeypatch)
        data = api.post("/api/v1/risk/evaluate", json=intent(quantity="1"), headers=headers()).json()
        assert data["assessment"] == "HALT" and "excess_order_notional" in data["reasons"]
        assert not data["order_permission"]


def test_market_failure_and_service_deadline_are_audited(tmp_path, monkeypatch):
    with client(tmp_path, service_timeout_seconds=0.02) as api:
        service, _ = prepare(api, monkeypatch)

        async def slow(*args, **kwargs):
            await asyncio.sleep(0.05)
            return inputs()[0]

        monkeypatch.setattr(service.atk, "observe", slow)
        response = api.post("/api/v1/risk/evaluate", json=intent(), headers=headers())
        assert response.status_code == 200
        data = response.json()
        assert data["assessment"] == "HALT" and "assessment_timeout" in data["reasons"]
        assert not data["order_permission"]
        assert api.get("/api/events").json()[-1]["type"] == "SERVICE_ASSESSMENT"


def test_rate_limit_is_before_expensive_calls(tmp_path, monkeypatch):
    with client(tmp_path, service_requests_per_minute=1) as api:
        _, calls = prepare(api, monkeypatch)
        assert api.post("/api/v1/risk/evaluate", json=intent(), headers=headers()).status_code == 200
        blocked = api.post("/api/v1/risk/evaluate", json=intent(), headers=headers())
        assert blocked.status_code == 429 and int(blocked.headers["Retry-After"]) > 0
        assert calls == ["observe"]


def test_model_status_cannot_leak_a_previous_assessments_success(tmp_path, monkeypatch):
    from aegis.models import Capability

    with client(tmp_path) as api:
        service, _ = prepare(api, monkeypatch)
        service.models.capabilities["EVREN"] = Capability(status="PASS")
        data = api.post("/api/v1/risk/evaluate", json=intent(), headers=headers()).json()
        assert data["evren_status"] == "FALLBACK"


def test_service_contract_export_does_not_rewrite_v2():
    from scripts.export_contract import additive_schema, check_frozen_v2

    schema = create_app().openapi()
    check_frozen_v2(schema)
    service = additive_schema(schema)
    assert set(service["paths"]) == {"/api/v1/risk/evaluate", "/api/v1/service"}
    assert "RiskAssessment" in service["components"]["schemas"]
    assert "AEGISServiceKey" in service["components"]["securitySchemes"]
    assert "Decision" not in service["components"]["schemas"]


def test_operational_halt_is_preserved_in_service_assessment(tmp_path, monkeypatch):
    with client(tmp_path) as api:
        service, _ = prepare(api, monkeypatch)

        async def classify(*args):
            return inputs()[1].model_copy(update={"label": "HALT"})

        monkeypatch.setattr(service.models, "classify", classify)
        data = api.post("/api/v1/risk/evaluate", json=intent(), headers=headers()).json()
        assert data["assessment"] == "HALT" and not data["order_permission"]


def test_large_and_chunked_bodies_are_rejected_before_provider_calls(tmp_path, monkeypatch):
    with client(tmp_path) as api:
        _, calls = prepare(api, monkeypatch)
        for content in (b"x" * 4096, iter([b"x" * 1500, b"y" * 1500])):
            response = api.post(
                "/api/v1/risk/evaluate",
                content=content,
                headers={**headers(), "Content-Type": "application/json"},
            )
            assert response.status_code == 413
        assert calls == []


def test_body_bound_holds_behind_asgi_root_path(tmp_path, monkeypatch):
    app = create_app(
        Settings(_env_file=None, db_path=tmp_path / "prefix.sqlite3", service_api_key=SERVICE_KEY)
    )
    with TestClient(app, root_path="/aegis") as api:
        _, calls = prepare(api, monkeypatch)
        padded = json.dumps(intent()).encode() + b" " * 3000
        response = api.post(
            "/aegis/api/v1/risk/evaluate",
            content=padded,
            headers={**headers(), "Content-Type": "application/json"},
        )
        assert response.status_code == 413
        assert calls == []
