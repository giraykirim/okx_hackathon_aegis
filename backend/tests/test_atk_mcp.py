import json

import pytest

from aegis.atk import ATK
from aegis.models import utcnow
from aegis.settings import Settings


def bridge_reply(*, ok=True, rows=None):
    timestamp = utcnow().isoformat()
    return {
        "discovery": {
            "request_ts": timestamp,
            "latency_ms": 2.5,
            "result": {"tools": [{"name": "market_get_ticker", "inputSchema": {"type": "object"}}]},
        },
        "call": {
            "request_ts": timestamp,
            "latency_ms": 7.5,
            "result": {
                "structuredContent": {
                    "tool": "market_get_ticker",
                    "ok": ok,
                    "data": {"data": rows or [{"instId": "BTC-USDT", "ts": "1792232297066"}]},
                    "capabilities": {"readOnly": True, "hasAuth": False},
                }
            },
        },
    }


@pytest.mark.asyncio
async def test_default_mcp_discovery_and_call_record_precise_evidence(monkeypatch):
    atk = ATK(Settings(_env_file=None))
    atk.begin_observation("mcp-run")
    seen = []

    async def execute(argv, *, private):
        seen.append(argv)
        assert not private
        return json.dumps(bridge_reply()).encode()

    monkeypatch.setattr(atk, "run_subprocess", execute)
    rows = await atk.call("ticker")
    assert rows[0]["instId"] == "BTC-USDT"
    assert any("atk-mcp-client.mjs" in arg for arg in seen[0])
    assert atk.market_receipts == []  # Never label MCP as a CLI receipt.
    events = atk.tool_events()
    call = next(e for e in events if e.details["tool_call"]["tool_id"].endswith("market_get_ticker"))
    evidence = call.details["tool_call"]
    assert evidence["run_id"] == "mcp-run" and evidence["evidence_id"] == call.id
    assert evidence["latency_ms"] == 7.5 and evidence["success"] is True
    assert evidence["source_ts"] == "2026-10-17T10:18:17.066000+00:00"
    assert evidence["status_code"] == "UNKNOWN"  # MCP did not expose HTTP status.
    assert len(evidence["response_hash"]) == 64
    assert atk.capabilities["ATK_MCP_LIST_TOOLS"].status == "PASS"
    assert atk.capabilities["ATK_MCP_CALL_TOOL"].evidence == [call.id]
    assert atk.capabilities["ATK_DEMO_ACCOUNT_READ"].status == "NOT_TESTED"


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["tool_error", "wrong_tool", "authenticated", "null", "wrong_symbol"])
async def test_mcp_untrusted_or_failed_result_is_not_a_success(monkeypatch, case):
    atk = ATK(Settings(_env_file=None))
    reply = bridge_reply()
    payload = reply["call"]["result"]["structuredContent"]
    if case == "tool_error":
        payload["ok"] = False
    elif case == "wrong_tool":
        payload["tool"] = "spot_place_order"
    elif case == "authenticated":
        payload["capabilities"]["hasAuth"] = True
    elif case == "null":
        payload["data"] = None
    else:
        payload["data"]["data"][0]["instId"] = "ETH-USDT"

    async def execute(*args, **kwargs):
        return json.dumps(reply).encode()

    monkeypatch.setattr(atk, "run_subprocess", execute)
    with pytest.raises(ValueError):
        await atk.call("ticker")
    assert atk.capabilities["ATK_MCP_CALL_TOOL"].status == "FAIL"
    failed = atk.tool_events()[-1].details["tool_call"]
    assert failed["success"] is False and failed["source_ts"] == "UNKNOWN"


@pytest.mark.asyncio
async def test_mcp_transport_failure_has_no_invented_response_or_source_time(monkeypatch):
    atk = ATK(Settings(_env_file=None))

    async def execute(*args, **kwargs):
        raise RuntimeError("provider credentials must not leak")

    monkeypatch.setattr(atk, "run_subprocess", execute)
    with pytest.raises(RuntimeError):
        await atk.call("ticker")
    event = atk.tool_events()[-1]
    evidence = event.details["tool_call"]
    assert evidence["response_hash"] == evidence["source_ts"] == evidence["status_code"] == "UNKNOWN"
    assert evidence["latency_ms"] >= 0 and evidence["success"] is False
    assert "credentials" not in event.model_dump_json()
    assert atk.capabilities["ATK_TR_ROUTING"].status != "PASS"


@pytest.mark.asyncio
async def test_cli_fallback_records_redacted_private_tool_call(monkeypatch):
    atk = ATK(Settings(_env_file=None, atk_transport="cli"))

    async def execute(*args, **kwargs):
        assert kwargs["private"]
        return b'[{"private_balance":"1000000","ccy":"USDT"}]'

    monkeypatch.setattr(atk, "run_subprocess", execute)
    await atk.call("balance")
    event = atk.tool_events()[-1]
    assert event.details["tool_call"]["success"] is True
    assert "1000000" not in event.model_dump_json()
    assert "private_balance" not in event.model_dump_json()
    assert event.details["payload_redacted"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("number", ["NaN", "Infinity", "1e999"])
async def test_nonfinite_numbers_are_rejected_with_failure_evidence(monkeypatch, number):
    atk = ATK(Settings(_env_file=None, atk_transport="cli"))

    async def execute(*args, **kwargs):
        return ('[{"last":' + number + "}]").encode()

    monkeypatch.setattr(atk, "run_subprocess", execute)
    with pytest.raises(ValueError):
        await atk.call("instruments")
    assert atk.tool_events()[-1].details["tool_call"]["success"] is False
    assert atk.tool_events()[-1].details["tool_call"]["response_hash"] == "UNKNOWN"


@pytest.mark.asyncio
async def test_agent_persists_tool_failure_even_when_cycle_deadline_expires(tmp_path, monkeypatch):
    from aegis.agent import Agent

    agent = Agent(Settings(_env_file=None, db_path=tmp_path / "deadline.sqlite3", cycle_timeout_seconds=0.01))

    async def execute(*args, **kwargs):
        import asyncio

        await asyncio.sleep(1)

    monkeypatch.setattr(agent.atk, "run_subprocess", execute)
    decision = await agent.cycle()
    records = [event for event in agent.store.events() if event["type"] == "tool_call"]
    assert records and any(event["details"]["tool_call"]["success"] is False for event in records)
    assert decision.execution_status == "NOT_SENT"
    await agent.close()


@pytest.mark.asyncio
async def test_prior_reconciliation_tool_records_use_current_run_id(tmp_path, monkeypatch):
    from aegis.agent import Agent

    agent = Agent(Settings(_env_file=None, source_mode="OKX_DEMO", db_path=tmp_path / "prior.sqlite3"))
    agent.run_id = "new-autonomous-run"

    async def reconcile():
        assert agent.atk.run_id == agent.run_id
        raise ValueError("Stop after attribution check")

    monkeypatch.setattr(agent, "reconcile_prior", reconcile)
    with pytest.raises(ValueError, match="Stop after attribution"):
        await agent.cycle()
    await agent.close()
