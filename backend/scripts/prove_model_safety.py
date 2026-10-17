"""Real public ATK NO_TRADE and separate injected MOCK HALT evidence; never places an order."""

import argparse
import asyncio
import json
import tempfile
from pathlib import Path

from aegis.agent import Agent
from aegis.atk_evidence import response_hash
from aegis.models import utcnow
from aegis.settings import ROOT, Settings


def pack(agent, decision, *, label, outcome, synthetic):
    events = agent.store.events(1000)
    phase_events = [event for event in events if event["details"].get("phase")]
    cycles = list(dict.fromkeys(event["details"]["cycle_id"] for event in phase_events))
    assert decision.execution_status == "NOT_SENT" and not decision.risk_approved
    assert decision.venue_order_id is None
    assert all(event["run_id"] == agent.run_id for event in events)
    assert all(event["details"]["correlation_id"] for event in phase_events)
    return agent.store.sanitize(
        {
            "label": label,
            "input_kind": "SYNTHETIC_INJECTED_MOCK" if synthetic else "REAL_PUBLIC_ATK",
            "source_mode": agent.settings.source_mode,
            "run_id": agent.run_id,
            "correlation_ids": cycles,
            "event_ids": [event["id"] for event in events],
            "events": events,
            "decision": decision.model_dump(mode="json"),
            "risk_veto_causes": decision.risk_reasons,
            "final_outcome": outcome,
            "exchange_writes_attempted": 0,
            "laya": agent.models.laya_metadata
            if not synthetic
            else {"source": "INJECTED_MOCK", "model_version": "MOCK-scripted"},
            "evren": agent.models.evren_metadata
            if not synthetic
            else {"source": "INJECTED_MOCK", "model": None},
            "capabilities": agent.capabilities(),
        }
    )


def verify_replay(proof):
    assert proof["payload_sha256"] == response_hash(proof["payload"])
    scenarios = proof["payload"]["scenarios"]
    for scenario in scenarios:
        assert scenario["decision"]["execution_status"] == "NOT_SENT"
        assert scenario["decision"]["venue_order_id"] is None
        assert set(scenario["event_ids"]) == {event["id"] for event in scenario["events"]}
        assert set(scenario["decision"]["evidence_ids"]) <= set(scenario["event_ids"])
    assert scenarios[0]["input_kind"] == "REAL_PUBLIC_ATK"
    assert any(event["type"] == "tool_call" for event in scenarios[0]["events"])
    assert scenarios[1]["input_kind"] == "SYNTHETIC_INJECTED_MOCK"
    assert "stale_feed" in scenarios[1]["risk_veto_causes"]
    assert "duplicate_intent" in scenarios[2]["risk_veto_causes"]


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "evidence/model-safety.json")
    parser.add_argument(
        "--replay", type=Path, help="Validate and summarize recorded evidence only; makes no network calls"
    )
    args = parser.parse_args()
    if args.replay:
        proof = json.loads(args.replay.read_text())
        verify_replay(proof)
        print("PASS: recorded evidence integrity and real/MOCK separation; replay makes no live calls")
        print(
            json.dumps(
                [
                    {k: item[k] for k in ("label", "input_kind", "run_id", "final_outcome")}
                    for item in proof["payload"]["scenarios"]
                ],
                indent=2,
            )
        )
        return
    local = Settings()
    scenarios = []
    with tempfile.TemporaryDirectory(prefix="aegis-model-safety-") as directory:
        public = local.model_copy(
            update={
                "source_mode": "MARKET_ONLY",
                "db_path": Path(directory) / "public.sqlite3",
                "demo_enabled": False,
                "demo_region_confirmed": False,
                "okx_demo_api_key": None,
                "okx_demo_secret_key": None,
                "okx_demo_passphrase": None,
            }
        )
        agent = Agent(public)
        try:
            await agent.start()
            async with asyncio.timeout(public.cycle_timeout_seconds + 5):
                while not agent.store.decisions():
                    await asyncio.sleep(0.1)
            await agent.stop()
            from aegis.models import Decision

            decision = Decision.model_validate(agent.store.decisions()[0])
            assert agent.atk.capabilities["ATK_MARKET"].status == "PASS", "Actual ATK market read failed"
            assert any(event["type"] == "NO_TRADE" for event in agent.store.events())
            scenarios.append(
                pack(agent, decision, label="A_REAL_ATK_NO_TRADE", outcome="NO_TRADE", synthetic=False)
            )
        finally:
            await agent.close()
        for fault in ("stale_feed", "duplicate_intent"):
            mock = Agent(
                Settings(_env_file=None, source_mode="MOCK", db_path=Path(directory) / (fault + ".sqlite3"))
            )
            try:
                mock.emit(
                    "FAULT_INJECTION",
                    "Explicit synthetic MOCK fault; no external model/venue invoked",
                    actor="proof-harness",
                    details={"fault": fault, "synthetic": True, "external_inputs_used": False},
                )
                if fault == "duplicate_intent":
                    warmup = await mock.cycle(fault)
                    assert warmup.venue_state == "MOCK_FILLED" and warmup.venue_order_id is None
                decision = await mock.cycle(fault)
                expected = "stale_feed" if fault == "stale_feed" else "duplicate_intent"
                assert expected in decision.risk_reasons
                assert not mock.models.journal.entries and not mock.atk.journal.entries
                scenarios.append(
                    pack(mock, decision, label="B_MOCK_" + fault.upper(), outcome="HALT", synthetic=True)
                )
            finally:
                await mock.close()
    payload = {
        "recorded_at": utcnow().isoformat(),
        "scenarios": scenarios,
        "optional_TR_demo_order": {
            "status": "NOT_TESTED",
            "reason": "Private TR demo eligibility/permissions unverified; this proof never submits orders",
        },
        "exchange_writes_attempted": 0,
        "live_execution": "DISABLED",
    }
    proof = {"payload": payload, "payload_sha256": response_hash(payload)}
    verify_replay(proof)
    args.output.write_text(json.dumps(proof, indent=2) + "\n")
    print(
        "PASS: real autonomous ATK -> analysis/fallback -> NO_TRADE; injected MOCK stale and duplicate -> HALT"
    )
    print("Evidence:", args.output)
    print(
        "Authenticated EVREN/LAYA and optional TR demo are only PASS if separately observed; absent configuration is NOT_TESTED"
    )


if __name__ == "__main__":
    asyncio.run(main())
