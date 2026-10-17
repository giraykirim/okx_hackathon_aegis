import argparse
import asyncio
import hashlib
import json
import tempfile
from pathlib import Path

import httpx

from aegis.agent import Agent
from aegis.models import utcnow
from aegis.settings import ROOT, Settings


async def main():
    parser = argparse.ArgumentParser(
        description="Read-only ATK + labeled local MOCK evidence. No exchange writes."
    )
    parser.add_argument("--output", type=Path, default=ROOT / "evidence" / "latest.json")
    args = parser.parse_args()
    evidence = {"recorded_at": utcnow().isoformat(), "exchange_writes_attempted": 0, "checks": {}}
    with tempfile.TemporaryDirectory(prefix="aegis-proof-") as directory:
        market = Agent(
            Settings(
                _env_file=None,
                source_mode="MARKET_ONLY",
                db_path=Path(directory) / "market.sqlite3",
                evren_api_key=None,
                laya_url=None,
                demo_enabled=False,
            )
        )
        decision = await market.cycle()
        observation = market.last_observation
        market_capability = market.capabilities()["ATK_MARKET"]
        evidence["checks"]["ATK_MARKET"] = {
            **market_capability,
            "observation": observation.model_dump(mode="json") if observation else None,
            "feed_age_seconds": (utcnow() - observation.observed_at).total_seconds() if observation else None,
            "decision": decision.model_dump(mode="json"),
            "events": market.store.events(),
        }
        assert decision.execution_status == "NOT_SENT" and not decision.risk_approved
        evidence["checks"]["MARKET_ONLY_NO_TRADE"] = {"status": "PASS", "decision_id": decision.id}
        await market.close()

        mock = Agent(Settings(_env_file=None, source_mode="MOCK", db_path=Path(directory) / "mock.sqlite3"))
        await mock.start()
        for _ in range(200):
            if mock.store.decisions():
                break
            await asyncio.sleep(0.01)
        await mock.stop()
        simulated = mock.store.decisions()[0]
        assert simulated["venue_state"] == "MOCK_FILLED" and simulated["execution_status"] == "NOT_SENT"
        # Restart the runtime to clear the stop request, preserving the durable audit journal.
        await mock.close()
        mock = Agent(Settings(_env_file=None, source_mode="MOCK", db_path=Path(directory) / "mock.sqlite3"))
        veto = await mock.cycle("stale_feed")
        assert not veto.risk_approved and "stale_feed" in veto.risk_reasons
        evidence["checks"]["AUTONOMOUS_MOCK"] = {
            "status": "PASS",
            "decision": simulated,
            "source_mode": "MOCK",
            "claim": "Local scripted observe/classify/reason/check/mock-execute/verify/audit cycle only",
        }
        evidence["checks"]["UNSAFE_SCENARIO"] = {"status": "PASS", "decision": veto.model_dump(mode="json")}
        evidence["checks"]["MOCK_AUDIT"] = {"events": mock.store.events(), "metrics": mock.store.metrics()}
        await mock.close()

    # Public schema and unauthenticated probe prove protocol availability, never account integration.
    try:
        async with httpx.AsyncClient(timeout=15, trust_env=False, follow_redirects=False) as client:
            response = await client.get("https://evren-llmapi.ssyz.org.tr/openapi.json")
            response.raise_for_status()
            schema = response.json()
            terms = schema["components"]["schemas"]["TermsStatus"]
            probe = await client.get("https://evren-llmapi.ssyz.org.tr/v1/terms/status")
            evidence["checks"]["EVREN_PUBLIC_PROTOCOL"] = {
                "status": "PASS",
                "openapi_sha256": hashlib.sha256(response.content).hexdigest(),
                "terms_status_schema": terms,
                "model_discovery_schema": schema["components"]["schemas"]["ModelListResponse"],
                "unauthenticated_terms_http_status": probe.status_code,
                "claim": "Public documentation retrieval only; no authenticated generation was tested",
            }
    except Exception as exc:
        evidence["checks"]["EVREN_PUBLIC_PROTOCOL"] = {"status": "FAIL", "error_type": type(exc).__name__}
    for name, reason in {
        "ATK_DEMO": "No isolated demo credentials or independent regional demo confirmation",
        "EVREN": "No local account API key; authenticated discovery and generation not tested",
        "LAYA": "RTX LAN endpoint unavailable; REVIEW/abstained advisory fallback",
        "LAYA_BENCHMARK": "Person 2 owns CUDA training and evaluation",
        "ERC8004": "Person 3 owns Fuji registration and owner/URI/receipt read-back",
    }.items():
        evidence["checks"][name] = {"status": "NOT_TESTED", "evidence": [reason]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "checks": {k: v.get("status", "RECORDED") for k, v in evidence["checks"].items()},
                "exchange_writes_attempted": 0,
            },
            indent=2,
        )
    )
    if market_capability["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
