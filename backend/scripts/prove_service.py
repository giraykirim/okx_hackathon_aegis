"""Capture actual local HTTP service calls and backend-generated ATK receipts. Never trades."""

import asyncio
import hashlib
import json

import httpx

from aegis.models import utcnow
from aegis.settings import ROOT, Settings


def verify_assessment(payload):
    unsigned = dict(payload)
    digest = unsigned.pop("assessment_sha256")
    assert (
        hashlib.sha256(json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        == digest
    )
    assert payload["execution_authority"] is False and payload["order_permission"] is False
    assert payload["source_mode"] == "MARKET_ONLY" and payload["account_provenance"] == "UNAVAILABLE"
    receipts = payload["market_provenance"]["receipts"]
    assert len(receipts) == 2 and all(r["status"] == "PASS" for r in receipts)
    assert {r["operation"] for r in receipts} == {"ticker", "instruments"}
    assert all(r["run_id"] == payload["run_id"] and r["result_sha256"] for r in receipts)
    assert next(r for r in receipts if r["operation"] == "ticker")["market_timestamp"]


async def main():
    settings = Settings()
    if not settings.service_api_key or not settings.control_token:
        raise SystemExit("Run scripts.init_local first; credentials remain local")
    proof = {
        "recorded_at": utcnow().isoformat(),
        "transport": "actual local HTTP",
        "public_deployment_status": "NOT_TESTED",
        "exchange_writes_attempted": 0,
        "checks": {},
    }
    headers = {"X-AEGIS-Key": settings.service_api_key.get_secret_value()}
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=50, trust_env=False) as client:
        health = (await client.get("/api/health")).json()
        assert health["source_mode"] == "MARKET_ONLY" and not health["running"]
        info = await client.get("/api/v1/service")
        info.raise_for_status()
        proof["service"] = info.json()
        assert proof["service"]["okx_ai"]["listing_status"] == "NOT_LISTED"
        unauthorized = await client.post(
            "/api/v1/risk/evaluate", json={"symbol": "BTC-USDT", "action": "BUY", "quantity": "0.0001"}
        )
        assert unauthorized.status_code == 401
        proof["checks"]["separate_auth"] = {"status": "PASS", "unauthenticated_http": 401}
        control_key = {"X-AEGIS-Key": settings.control_token.get_secret_value()}
        assert (
            await client.post(
                "/api/v1/risk/evaluate",
                headers=control_key,
                json={"symbol": "BTC-USDT", "action": "BUY", "quantity": "0.0001"},
            )
        ).status_code == 401
        spoofed = await client.post(
            "/api/v1/risk/evaluate",
            headers=headers,
            json={"symbol": "BTC-USDT", "action": "BUY", "quantity": "0.0001", "account_known": True},
        )
        assert spoofed.status_code == 422
        proof["checks"]["caller_flag_rejection"] = {"status": "PASS", "http": 422}
        before = (await client.get("/api/metrics")).json()
        for name, quantity in (("small_intent", "0.0001"), ("excess_notional", "1")):
            response = await client.post(
                "/api/v1/risk/evaluate",
                headers=headers,
                json={
                    "symbol": "BTC-USDT",
                    "action": "BUY",
                    "quantity": quantity,
                    "client_request_id": "proof-" + name,
                },
            )
            response.raise_for_status()
            payload = response.json()
            verify_assessment(payload)
            if name == "excess_notional":
                assert payload["assessment"] == "HALT" and "excess_order_notional" in payload["reasons"]
            proof["checks"][name] = {"status": "PASS", "response": payload}
        after = (await client.get("/api/metrics")).json()
        assert after == before, "Assessments must not create trading decisions or orders"
        proof["checks"]["no_trading_side_effects"] = {"status": "PASS", "before": before, "after": after}
        events = (await client.get("/api/events?limit=1000")).json()
        ids = {proof["checks"][name]["response"]["run_id"] for name in ("small_intent", "excess_notional")}
        service_events = [e for e in events if e["run_id"] in ids]
        assert sum(e["type"] == "ATK_RECEIPT" for e in service_events) == 4
        assert sum(e["type"] == "SERVICE_ASSESSMENT" for e in service_events) == 2
        proof["events"] = service_events
    path = ROOT / "evidence/amendment-http.json"
    path.write_text(json.dumps(proof, indent=2) + "\n")
    print(
        "PASS: real HTTP service, server ATK receipts/hashes, spoof rejection, separate auth, HALT, no trades"
    )
    print("Evidence: backend/evidence/amendment-http.json; public deployment remains NOT_TESTED")


if __name__ == "__main__":
    asyncio.run(main())
