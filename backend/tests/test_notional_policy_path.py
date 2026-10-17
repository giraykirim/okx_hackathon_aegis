"""Notional service must execute the same deterministic policy as the agent."""

from datetime import timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from test_policy import inputs

from aegis.app import create_app
from aegis.settings import Settings


def api(tmp_path):
    return TestClient(
        create_app(
            Settings(
                _env_file=None, db_path=tmp_path / "service.sqlite3", service_api_key="unit-assessment-only"
            )
        )
    )


def payload():
    return {
        "request_id": "policy-path",
        "symbol": "BTC-USDT",
        "proposed_action": "BUY",
        "proposed_notional": "10",
    }


def test_real_notional_path_calls_gate_and_discards_accidental_account_data(tmp_path, monkeypatch):
    import aegis.notional_service as module
    from aegis.policy import check

    calls = []

    def gate(observation, classification, proposal, **kwargs):
        calls.append((observation, proposal, kwargs))
        return check(observation, classification, proposal, **kwargs)

    monkeypatch.setattr(module, "check", gate)
    with api(tmp_path) as client:

        async def observe():
            return inputs()[0]  # Synthetic known-account adapter result must be discarded.

        monkeypatch.setattr(client.app.state.risk_service.atk, "observe", observe)
        response = client.post(
            "/api/v1/risk/evaluate", json=payload(), headers={"X-AEGIS-Key": "unit-assessment-only"}
        )
        assert response.status_code == 200 and response.json()["verdict"] == "UNAVAILABLE"
        assert len(calls) == 1
        observation, proposal, kwargs = calls[0]
        assert observation.account_known is False and observation.quote_available == 0
        assert kwargs["source_mode"] == "MARKET_ONLY" and kwargs["approval_available"] is False
        assert proposal.quantity > 0 and proposal.quantity % observation.lot_size == 0
        result = response.json()
        assert "DETERMINISTIC_POLICY_EVALUATED" in result["reason_codes"]
        assert "INSUFFICIENT_QUOTE" not in result["reason_codes"]
        audit = client.get("/api/events").json()[-1]
        assert audit["details"]["policy_latency_ms"] >= 0
        assert audit["details"]["quantity_source"] == "SERVER_DERIVED_FROM_PUBLIC_MARKET_NOT_EXECUTABLE"


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"observed_at": inputs()[3] - timedelta(seconds=40)}, "STALE_FEED"),
        ({"observed_at": inputs()[3] + timedelta(seconds=40)}, "FUTURE_FEED"),
        ({"min_size": Decimal("1")}, "INVALID_QUANTITY"),
        ({"bid": Decimal("60000")}, "CROSSED_QUOTES"),
    ],
)
def test_notional_uses_real_gate_vetoes(tmp_path, monkeypatch, change, reason):
    with api(tmp_path) as client:

        async def observe():
            return inputs()[0].model_copy(update=change)

        monkeypatch.setattr(client.app.state.risk_service.atk, "observe", observe)
        response = client.post(
            "/api/v1/risk/evaluate", json=payload(), headers={"X-AEGIS-Key": "unit-assessment-only"}
        )
        assert response.json()["verdict"] == "BLOCK"
        assert reason in response.json()["reason_codes"]
        assert response.json()["execution_authorized"] is False
