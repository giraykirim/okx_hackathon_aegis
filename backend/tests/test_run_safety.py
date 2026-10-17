from decimal import Decimal

import pytest
from test_policy import gate, inputs

from aegis.agent import Agent
from aegis.settings import Settings
from aegis.store import Store


@pytest.mark.parametrize("symbol", ["BTC-USDC", "BTC-EUR", "ETH-USDT"])
def test_matching_but_unallowlisted_symbols_cannot_authorize_trade(symbol):
    result = gate(observation={"symbol": symbol}, proposal={"symbol": symbol})
    assert not result.approved and "symbol_not_allowed" in result.reasons


def test_corrupt_observation_is_a_deterministic_veto():
    result = gate(observation={"price": Decimal("NaN")})
    assert not result.approved and "corrupt_data" in result.reasons


def test_run_budget_reservation_is_atomic_durable_and_uses_decimal(tmp_path):
    path = tmp_path / "budget.sqlite3"
    a, b = Store(path), Store(path)
    first = inputs()[2]
    second = first.model_copy(update={"intent_id": "different-intent"})
    args = {
        "run_id": "one-run",
        "reserved_notional": Decimal("15.01"),
        "max_run_notional": Decimal("25"),
        "max_run_orders": 3,
    }
    assert a.claim(first, "client-a", "MOCK", **args)
    a.order_status(first.intent_id, "NOT_SENT")
    assert not b.claim(second, "client-b", "MOCK", **args)
    a.close()
    b.close()
    reopened = Store(path)
    assert reopened.run_budget("one-run") == (1, Decimal("15.01"))
    assert reopened.claim(second, "client-b", "MOCK", **{**args, "run_id": "new-run"})
    reopened.close()


@pytest.mark.asyncio
async def test_autonomous_fresh_intents_cannot_exceed_run_order_budget(tmp_path, monkeypatch):
    agent = Agent(
        Settings(_env_file=None, source_mode="MOCK", db_path=tmp_path / "run.sqlite3", max_run_orders=1)
    )
    assert (await agent.cycle()).risk_approved
    # The second proposal has a new intent; per-intent deduplication alone would allow it.
    second = await agent.cycle()
    assert not second.risk_approved and "run_budget_exhausted" in second.risk_reasons
    assert second.execution_status == "NOT_SENT" and agent.mock_execution_count == 1
    await agent.close()
