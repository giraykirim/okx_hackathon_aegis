"""Exercise a running local MARKET_ONLY backend, including actual SSE replay."""

import asyncio
import json
from pathlib import Path

import httpx

from aegis.models import utcnow
from aegis.settings import ROOT, Settings


async def main():
    settings = Settings()
    if not settings.control_token:
        raise SystemExit("Initialize backend/.env locally first")
    headers = {"Authorization": "Bearer " + settings.control_token.get_secret_value()}
    proof = {"recorded_at": utcnow().isoformat(), "source_mode": "MARKET_ONLY", "checks": {}}
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=10, trust_env=False) as client:
        health = (await client.get("/api/health")).json()
        assert health["source_mode"] == "MARKET_ONLY", "Smoke tool only permits read-only real-market mode"
        proof["checks"]["read_routes"] = {}
        for route in (
            "health",
            "snapshot",
            "events",
            "decisions",
            "metrics",
            "web3/identity",
            "capabilities",
        ):
            response = await client.get("/api/" + route)
            response.raise_for_status()
            proof["checks"]["read_routes"][route] = response.status_code
        unauthorized = await client.post("/api/agent/start")
        assert unauthorized.status_code == 401
        proof["checks"]["unauthenticated_control"] = "PASS: HTTP 401"
        response = await client.post("/api/demo/scenario", headers=headers, json={"scenario": "normal"})
        assert response.status_code == 409
        proof["checks"]["scenario_mode_isolation"] = "PASS: HTTP 409"
        initial = (await client.get("/api/events")).json()
        previous_id = initial[-1]["id"] if initial else None
        start = await client.post("/api/agent/start", headers=headers)
        start.raise_for_status()
        run_id = start.json()["run_id"]
        try:
            for _ in range(150):
                decisions = (await client.get("/api/decisions")).json()
                if any(d["run_id"] == run_id for d in decisions):
                    break
                await asyncio.sleep(0.2)
            else:
                raise AssertionError("No autonomous decision within 30 seconds")
        finally:
            stop = await client.post("/api/agent/stop", headers=headers)
            stop.raise_for_status()
            assert not stop.json()["running"]
        snapshot = (await client.get("/api/snapshot")).json()
        assert snapshot["latest_decision"]["run_id"] == run_id
        assert snapshot["latest_decision"]["execution_status"] == "NOT_SENT"
        assert snapshot["capabilities"]["ATK_MARKET"]["status"] == "PASS"
        events = (await client.get("/api/events")).json()
        cursor = previous_id or events[0]["id"]
        expected = next(event for i, event in enumerate(events) if i and events[i - 1]["id"] == cursor)
        async with client.stream("GET", "/api/stream", headers={"Last-Event-ID": cursor}) as response:
            assert response.headers["content-type"].startswith("text/event-stream")
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    streamed = json.loads(line[6:])
                    assert streamed["id"] == expected["id"]
                    proof["checks"]["sse_resume"] = {"status": "PASS", "event_id": streamed["id"]}
                    break
        proof["checks"]["autonomous_http_cycle"] = {"status": "PASS", "snapshot": snapshot, "events": events}
    path: Path = ROOT / "evidence" / "http-smoke.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(proof, indent=2) + "\n")
    print(
        "PASS: real HTTP read routes, authenticated start/stop, autonomous ATK NO_TRADE, mode isolation, SSE resume"
    )
    print("Evidence saved to backend/evidence/http-smoke.json; no secrets displayed")


if __name__ == "__main__":
    asyncio.run(main())
