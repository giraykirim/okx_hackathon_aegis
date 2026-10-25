import json
from types import SimpleNamespace

import pytest
from pydantic import AwareDatetime, TypeAdapter
from test_policy import inputs
from test_service import client, headers, intent, prepare

_TIMESTAMP = TypeAdapter(AwareDatetime)


def assess(tmp_path, monkeypatch, observation):
    with client(tmp_path) as api:
        service, calls = prepare(api, monkeypatch, observation=observation)

        async def classify(*args, **kwargs):
            calls.append("classify")
            return inputs()[1]

        async def reason(*args, **kwargs):
            calls.append("reason")
            return SimpleNamespace(summary="Deterministic offline summary")

        monkeypatch.setattr(service.models, "classify", classify)
        monkeypatch.setattr(service.models, "reason", reason)
        response = api.post("/api/v1/risk/evaluate", json=intent(), headers=headers())
    return response, calls


# Serializing the unvalidated string emits a Pydantic UserWarning; the response contract is under test.
@pytest.mark.filterwarnings("ignore::UserWarning")
def test_corrupt_observed_at_is_audited_halt_without_unverified_market_timestamp(tmp_path, monkeypatch):
    obs = inputs()[0].model_copy(update={"observed_at": "invalid-timestamp"})
    response, calls = assess(tmp_path, monkeypatch, obs)
    assert response.status_code == 200, response.text
    data = response.json()
    assert calls == ["observe", "classify", "reason"]
    assert data["assessment"] == "HALT"
    assert "corrupt_data" in data["reasons"]
    assert data["market_checks"]["status"] == "FAIL"
    assert "corrupt_data" in data["market_checks"]["reasons"]
    assert data["market_provenance"]["status"] == "FAIL"
    assert data["market_provenance"]["market_timestamp"] is None
    assert data["execution_authority"] is False and data["order_permission"] is False


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_corrupt_observed_at_audit_record_matches_response_without_the_raw_value(tmp_path, monkeypatch):
    obs = inputs()[0].model_copy(update={"observed_at": "invalid-timestamp"})
    with client(tmp_path) as api:
        service, calls = prepare(api, monkeypatch, observation=obs)

        async def classify(*args, **kwargs):
            return inputs()[1]

        async def reason(*args, **kwargs):
            return SimpleNamespace(summary="Deterministic offline summary")

        monkeypatch.setattr(service.models, "classify", classify)
        monkeypatch.setattr(service.models, "reason", reason)
        response = api.post("/api/v1/risk/evaluate", json=intent(), headers=headers())
        events = api.app.state.agent.store.events(1000)
    assert response.status_code == 200, response.text
    audits = [e for e in events if e["type"] == "SERVICE_ASSESSMENT"]
    assert len(audits) == 1 and audits[0]["details"] == response.json()
    assert audits[0]["details"]["assessment"] == "HALT"
    assert audits[0]["details"]["market_provenance"]["market_timestamp"] is None
    assert "invalid-timestamp" not in json.dumps(events)


def test_healthy_observation_keeps_pass_provenance_and_original_timestamp(tmp_path, monkeypatch):
    obs = inputs()[0]
    response, calls = assess(tmp_path, monkeypatch, obs)
    assert response.status_code == 200, response.text
    data = response.json()
    assert calls == ["observe", "classify", "reason"]
    assert data["assessment"] == "REVIEW"
    assert "corrupt_data" not in data["reasons"]
    assert data["market_checks"]["status"] == "PASS"
    assert data["market_provenance"]["status"] == "PASS"
    assert _TIMESTAMP.validate_python(data["market_provenance"]["market_timestamp"]) == obs.observed_at
    assert data["execution_authority"] is False and data["order_permission"] is False
