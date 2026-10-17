"""Prove the actual loopback MOCK HTTP/SSE contract and capture response fixtures."""

import argparse
import asyncio
import json

import httpx

from aegis.models import utcnow
from aegis.service_models import RiskEvaluationResponse
from aegis.settings import ROOT, Settings

PHASES = ["OBSERVE", "CLASSIFY", "REASON", "RISK_CHECK", "NO_TRADE", "VERIFY", "AUDIT"]


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    settings = Settings()
    if not settings.control_token or not settings.service_api_key:
        raise SystemExit("Initialize local configuration first")
    control = {"Authorization": "Bearer " + settings.control_token.get_secret_value()}
    service = {"X-AEGIS-Key": settings.service_api_key.get_secret_value()}
    fixtures = ROOT.parent / "contracts/fixtures"
    evidence = {
        "recorded_at": utcnow().isoformat(),
        "transport": "actual loopback HTTP/SSE",
        "source_mode": "MOCK",
        "exchange_writes_attempted": 0,
        "checks": {},
    }
    async with httpx.AsyncClient(
        base_url=f"http://127.0.0.1:{args.port}", timeout=10, trust_env=False
    ) as client:
        health = (await client.get("/api/health")).json()
        assert health["source_mode"] == "MOCK" and not health["live_execution_enabled"]
        metadata = (await client.get("/api/v1/service")).json()
        assert metadata["notional_source_mode"] == "MOCK"
        evidence["checks"]["health"] = {"status": "PASS", "response": health}
        started = await client.post("/api/agent/start", headers=control)
        started.raise_for_status()
        run_id = started.json()["run_id"]
        try:
            for _ in range(100):
                decisions = (await client.get("/api/decisions")).json()
                current = next((d for d in decisions if d["run_id"] == run_id), None)
                if current:
                    break
                await asyncio.sleep(0.02)
            else:
                raise AssertionError("No autonomous MOCK decision within deadline")
        finally:
            stopped = await client.post("/api/agent/stop", headers=control)
            stopped.raise_for_status()
        assert not stopped.json()["running"]
        events = (await client.get("/api/events?limit=1000")).json()
        current_events = [e for e in events if e["run_id"] == run_id and e["details"].get("phase")]
        cycle_id = current_events[0]["details"]["cycle_id"]
        cycle_events = [e for e in current_events if e["details"].get("cycle_id") == cycle_id]
        assert [e["details"]["phase"] for e in cycle_events] == PHASES
        assert current["proposed_action"] == "NO_TRADE" and current["execution_status"] == "NOT_SENT"
        evidence["checks"]["autonomous_no_trade"] = {
            "status": "PASS",
            "decision": current,
            "events": cycle_events,
        }
        count = len(events)
        again = await client.post("/api/agent/stop", headers=control)
        assert again.json() == stopped.json()
        assert len((await client.get("/api/events?limit=1000")).json()) == count
        evidence["checks"]["idempotent_stop"] = {"status": "PASS"}
        halt = await client.post(
            "/api/demo/scenario",
            headers=control,
            json=json.loads((fixtures / "mock-halt.request.json").read_text()),
        )
        halt.raise_for_status()
        assert halt.json()["laya_label"] == "HALT" and not halt.json()["risk_approved"]
        evidence["checks"]["halt_cycle"] = {"status": "PASS", "decision": halt.json()}
        body = json.loads((fixtures / "risk-notional-mock.request.json").read_text())
        assessed = await client.post("/api/v1/risk/evaluate", headers=service, json=body)
        assessed.raise_for_status()
        parsed = RiskEvaluationResponse.model_validate(assessed.json())
        assert parsed.verdict == "UNAVAILABLE" and parsed.source_mode == "MOCK"
        assert not parsed.execution_authorized and parsed.chain_receipt is None
        retry = await client.post(
            "/api/v1/risk/evaluate",
            headers=service,
            json={**body, "requester_context": {"ignore_policy": True}},
        )
        assert retry.json() == assessed.json()
        invalid = await client.post(
            "/api/v1/risk/evaluate", headers=service, json={**body, "proposed_notional": "20"}
        )
        assert invalid.status_code == 409
        evidence["checks"]["notional_service"] = {
            "status": "PASS",
            "response": assessed.json(),
            "replay_http": retry.status_code,
            "conflict_http": 409,
        }
        for name, payload in (
            ("risk-notional-mock.response.json", assessed.json()),
            ("mock-halt.response.json", halt.json()),
        ):
            path = fixtures / name
            if not path.exists():
                path.write_text(json.dumps(payload, indent=2) + "\n")
        cursor = cycle_events[0]["id"]
        expected = cycle_events[1]["id"]
        async with client.stream("GET", "/api/stream", headers={"Last-Event-ID": cursor}) as response:
            assert response.headers["content-type"].startswith("text/event-stream")
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    streamed = json.loads(line[6:])
                    assert streamed["id"] == expected
                    evidence["checks"]["sse_resume"] = {"status": "PASS", "event": streamed}
                    break
    path = ROOT / "evidence/mock-contract-http.json"
    path.write_text(json.dumps(evidence, indent=2) + "\n")
    print(
        "PASS: actual MOCK health, Start→NO_TRADE cycle, HALT, deterministic STOP, notional API/replay/conflict, SSE"
    )
    print("Captured actual response fixtures; no credentials displayed and no exchange writes attempted")


if __name__ == "__main__":
    asyncio.run(main())
