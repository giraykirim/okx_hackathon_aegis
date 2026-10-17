"""Explicit bounded loopback HTTP proof. MARKET_ONLY; no exchange writes."""

import asyncio
import json
import time

import httpx

from aegis.models import new_id, utcnow
from aegis.settings import ROOT, Settings


async def main():
    settings = Settings()
    assert settings.source_mode == "MARKET_ONLY" and not settings.demo_ready()
    front_env = {}
    for line in (ROOT.parent / "frontend/.env.local").read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            front_env[key] = value.strip().strip('"')
    admin = {"X-AEGIS-Admin-Secret": front_env["AEGIS_DASHBOARD_ADMIN_SECRET"]}
    service = {"X-AEGIS-Key": settings.service_api_key.get_secret_value()}
    async with httpx.AsyncClient(trust_env=False, timeout=40) as client:
        b = "http://127.0.0.1:8000"
        f = "http://127.0.0.1:3000"
        health = (await client.get(b + "/api/health")).json()
        assert health["running"] is False and health["live_execution_enabled"] is False
        controls = []
        for path in ("start", "stop"):
            r = await client.post(f + "/api/agent/" + path)
            assert r.status_code == 401
            controls.append({"path": path, "unauthenticated_http_status": r.status_code})
        started = time.monotonic()
        r = await client.post(f + "/api/agent/start", headers=admin)
        r.raise_for_status()
        snapshot = (await client.get(b + "/api/snapshot")).json()
        run_id = snapshot["run_id"]
        try:
            while time.monotonic() - started < 65:
                snapshot = (await client.get(b + "/api/snapshot")).json()
                decision = snapshot.get("latest_decision")
                if decision and decision["run_id"] == run_id:
                    break
                await asyncio.sleep(0.5)
            else:
                raise AssertionError("Bounded autonomous cycle deadline")
        finally:
            r = await client.post(f + "/api/agent/stop", headers=admin)
            r.raise_for_status()
        snapshot = (await client.get(b + "/api/snapshot")).json()
        decision = snapshot["latest_decision"]
        assert decision["run_id"] == run_id and decision["execution_status"] == "NOT_SENT"
        assert decision["venue_order_id"] is None and not decision["risk_approved"]
        events = (await client.get(b + "/api/events?limit=1000")).json()
        events = [e for e in events if e["run_id"] == run_id]
        assessments = []
        for notional in ("10", "26"):
            request = {
                "request_id": "jury-" + new_id(),
                "symbol": "BTC-USDT",
                "proposed_action": "BUY",
                "proposed_notional": notional,
            }
            missing = await client.post(b + "/api/v1/risk/evaluate", json=request)
            assert missing.status_code == 401
            response = await client.post(b + "/api/v1/risk/evaluate", json=request, headers=service)
            response.raise_for_status()
            data = response.json()
            assert data["execution_authorized"] is False
            assert "DETERMINISTIC_POLICY_EVALUATED" in data["reason_codes"]
            assert data["verdict"] == ("UNAVAILABLE" if notional == "10" else "BLOCK")
            replay = await client.post(b + "/api/v1/risk/evaluate", json=request, headers=service)
            assert replay.json() == data
            conflict = await client.post(
                b + "/api/v1/risk/evaluate", json={**request, "proposed_notional": "11"}, headers=service
            )
            assert conflict.status_code == 409
            assessments.append(
                {
                    "request": request,
                    "response": data,
                    "http_status": response.status_code,
                    "idempotency_replay": "PASS",
                    "changed_intent_http_status": 409,
                    "missing_auth_http_status": 401,
                }
            )
        health = (await client.get(b + "/api/health")).json()
        assert not health["running"]
        report = {
            "recorded_at": utcnow().isoformat(),
            "evidence_kind": "REAL_LOOPBACK_HTTP_WITH_PUBLIC_ATK_AND_LAN_MODELS",
            "source_mode": "MARKET_ONLY",
            "run_id": run_id,
            "snapshot": snapshot,
            "events": events,
            "phase_timeline": [e["details"]["phase"] for e in events if "phase" in e["details"]],
            "control_auth": controls,
            "assessments": assessments,
            "health_after_stop": health,
            "exchange_writes_attempted": 0,
            "operator_keys_exported": False,
        }
        (ROOT / "evidence/system-status-http.json").write_text(json.dumps(report, indent=2) + "\n")
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "run_id": run_id,
                    "phases": report["phase_timeline"],
                    "outcome": decision["execution_status"],
                    "laya": snapshot["classification"],
                    "risk_service_verdicts": [x["response"]["verdict"] for x in assessments],
                    "agent_stopped": not health["running"],
                    "exchange_writes_attempted": 0,
                }
            )
        )


if __name__ == "__main__":
    asyncio.run(main())
