"""OFFLINE_BACKEND_TEST: injected transports, never genuine ATK/exchange output."""

import asyncio
import json
import os
import socket
import subprocess
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from test_policy import inputs

from aegis.agent import Agent
from aegis.atk import ATK
from aegis.models import Capability
from aegis.policy import check
from aegis.settings import Settings

RECORDS = []


@pytest.fixture(autouse=True)
def isolate(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("OFFLINE_BACKEND_TEST forbids network/process execution")

    for method in ("connect", "connect_ex"):
        monkeypatch.setattr(socket.socket, method, denied)
    monkeypatch.setattr(subprocess, "Popen", denied)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", denied)
    monkeypatch.setattr(asyncio, "create_subprocess_shell", denied)


def record(scenario, **outcome):
    RECORDS.append(
        dict(
            evidence_kind="OFFLINE_BACKEND_TEST",
            source_event=scenario,
            scenario=scenario,
            derivative_group=scenario,
            independent_incident=False,
            real_network_calls=0,
            real_submission_calls=0,
            **outcome,
        )
    )


@pytest.fixture(scope="module", autouse=True)
def export_proof():
    RECORDS.clear()
    yield
    if path := os.environ.get("AEGIS_OFFLINE_PROOF_PATH"):
        Path(path).write_text(
            json.dumps(
                dict(
                    evidence_kind="OFFLINE_BACKEND_TEST",
                    network_and_subprocess_denied=True,
                    contains_private_logs=False,
                    new_seed_timestamp_or_id_is_independent_event=False,
                    traces=RECORDS,
                ),
                indent=2,
            )
            + "\n"
        )


def runtime(tmp_path):
    return Agent(Settings(_env_file=None, source_mode="OKX_DEMO", db_path=tmp_path / "offline.sqlite3"))


async def install(agent, monkeypatch):
    async def observe():
        obs = inputs()[0]
        obs.account_observed_at = obs.observed_at
        return obs

    async def classify(*args, **kwargs):
        agent.models.capabilities["LAYA"] = Capability(status="PASS")
        return inputs()[1]

    async def reason(*args):
        agent.models.capabilities["EVREN"] = Capability(status="PASS")
        return inputs()[2]

    monkeypatch.setattr(agent.atk, "observe", observe)
    monkeypatch.setattr(agent.models, "classify", classify)
    monkeypatch.setattr(agent.models, "reason", reason)
    monkeypatch.setattr(Settings, "demo_ready", lambda self: True)


@pytest.mark.asyncio
async def test_pre_submit_read_timeout(tmp_path, monkeypatch):
    agent = runtime(tmp_path)

    async def failed():
        raise TimeoutError()

    monkeypatch.setattr(agent.atk, "observe", failed)
    out = await agent.cycle()
    assert out.execution_status == "NOT_SENT" and not agent.store.unresolved()
    record("pre_submit_read_timeout", execution_status=out.execution_status, unresolved=False)
    await agent.close()


@pytest.mark.asyncio
async def test_post_submit_unknown_no_retry(tmp_path, monkeypatch):
    agent = runtime(tmp_path)
    await install(agent, monkeypatch)
    attempts = []

    async def submit(*args):
        attempts.append(True)
        raise TimeoutError()

    async def read(*args):
        raise TimeoutError()

    monkeypatch.setattr(agent.atk, "place", submit)
    monkeypatch.setattr(agent.atk, "reconcile", read)
    first = await agent.cycle()
    second = await agent.cycle()
    assert first.execution_status == "UNKNOWN" and len(attempts) == 1
    assert second.execution_status == "NOT_SENT" and "unresolved_prior_order" in second.risk_reasons
    record(
        "post_submit_unknown_retry",
        execution_status=first.execution_status,
        simulated_submits=1,
        retry_vetoes=second.risk_reasons,
    )
    await agent.close()


@pytest.mark.asyncio
async def test_revocation_before_gate(tmp_path, monkeypatch):
    agent = runtime(tmp_path)
    await install(agent, monkeypatch)

    async def reason(*args):
        agent.models.capabilities["EVREN"] = Capability(status="PASS")
        monkeypatch.setattr(Settings, "demo_ready", lambda self: False)
        return inputs()[2]

    monkeypatch.setattr(agent.models, "reason", reason)
    out = await agent.cycle()
    assert not out.risk_approved and "approval_unavailable" in out.risk_reasons
    record("permission_revoked", execution_status=out.execution_status, vetoes=out.risk_reasons)
    await agent.close()


@pytest.mark.parametrize(
    "name,age,approval,duplicate,unresolved,reason",
    [
        ("stale", 40, True, False, False, "stale_feed"),
        ("future", -2.1, True, False, False, "future_feed"),
        ("missing_approval", 0, False, False, False, "approval_unavailable"),
        ("duplicate", 0, True, True, False, "duplicate_intent"),
        ("unresolved_ack", 0, True, False, True, "unresolved_prior_order"),
    ],
)
def test_vetoes_survive_model_continue(name, age, approval, duplicate, unresolved, reason):
    obs, laya, proposal, now = inputs()
    obs.observed_at = now - timedelta(seconds=age)
    out = check(
        obs,
        laya,
        proposal,
        now=now,
        source_mode="MOCK",
        approval_available=approval,
        duplicate=duplicate,
        unresolved=unresolved,
    )
    assert not out.approved and reason in out.reasons
    record(name, risk_approved=False, vetoes=out.reasons)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "state,expected",
    [
        ("live", "PENDING"),
        ("partially_filled", "PENDING"),
        ("filled", "VERIFIED"),
        ("canceled", "VERIFIED"),
        ("unrecognized", None),
    ],
)
async def test_venue_states(state, expected, monkeypatch):
    atk = ATK(Settings(_env_file=None))
    proposal = inputs()[2]

    async def read(*args):
        return [
            dict(
                instId="BTC-USDT",
                clOrdId="a" * 32,
                side="buy",
                sz=str(proposal.quantity),
                ordId="OFFLINE_SYNTHETIC",
                ordType="ioc",
                tdMode="cash",
                px="50501.1",
                state=state,
            )
        ]

    monkeypatch.setattr(atk, "call", read)
    if expected is None:
        with pytest.raises(ValueError):
            await atk.reconcile(proposal, "a" * 32, Decimal("50501.1"))
        record("venue_" + state, verification_rejected=True)
    else:
        status, _, venue = await atk.reconcile(proposal, "a" * 32, Decimal("50501.1"))
        assert status == expected and venue == state
        record("venue_" + state, execution_status=status, venue_state=venue, filled=venue == "filled")


@pytest.mark.asyncio
async def test_ack_duplicate_retry(tmp_path, monkeypatch):
    agent = runtime(tmp_path)
    await install(agent, monkeypatch)
    sends = []

    async def submit(*args):
        sends.append(True)
        return "OFFLINE_SYNTHETIC"

    async def read(*args):
        return "PENDING", "OFFLINE_SYNTHETIC", "live"

    monkeypatch.setattr(agent.atk, "place", submit)
    monkeypatch.setattr(agent.atk, "reconcile", read)
    first = await agent.cycle()
    second = await agent.cycle()
    assert first.execution_status == "PENDING" and len(sends) == 1
    # Backend-owned intent IDs: the retry is blocked by the unresolved prior submission.
    assert not second.risk_approved and "unresolved_prior_order" in second.risk_reasons
    record(
        "ack_duplicate_retry",
        execution_status=first.execution_status,
        filled=False,
        simulated_submits=1,
        retry_vetoes=second.risk_reasons,
    )
    await agent.close()


@pytest.mark.asyncio
async def test_safe_no_trade(tmp_path):
    agent = Agent(
        Settings(
            _env_file=None,
            source_mode="MOCK",
            db_path=tmp_path / "mock.sqlite3",
            mock_autonomous_scenario="no_trade",
        )
    )
    out = await agent.cycle()
    assert out.execution_status == "NOT_SENT" and not out.risk_approved and agent.mock_execution_count == 0
    record(
        "safe_no_trade",
        execution_status=out.execution_status,
        risk_approved=False,
        event_phases=[e["type"] for e in agent.store.events()],
    )
    await agent.close()
