from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError


def inputs():
    from aegis.models import Classification, Observation, Proposal

    now = datetime.now(timezone.utc)
    return (
        Observation(
            symbol="BTC-USDT",
            observed_at=now,
            price="50000",
            ask="50001",
            bid="49999",
            min_size="0.00001",
            lot_size="0.00000001",
            instrument_live=True,
            account_known=True,
            exposure_quote="0",
            quote_available="1000",
            base_available="0.1",
        ),
        Classification(
            label="CONTINUE", confidence=0.99, abstained=False, model_version="test", latency_ms=1
        ),
        Proposal(action="BUY", symbol="BTC-USDT", quantity="0.0001", intent_id="test-intent", summary="test"),
        now,
    )


def gate(**kwargs):
    from aegis.policy import check

    obs, laya, proposal, now = inputs()
    obs = obs.model_copy(update=kwargs.pop("observation", {}))
    laya = laya.model_copy(update=kwargs.pop("classification", {}))
    proposal = proposal.model_copy(update=kwargs.pop("proposal", {}))
    return check(
        obs,
        laya,
        proposal,
        now=now,
        source_mode="MOCK",
        approval_available=True,
        unresolved=False,
        duplicate=False,
        **kwargs,
    )


def test_valid_small_mock_order_is_allowed():
    assert gate().approved


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"observed_at": datetime.now(timezone.utc) - timedelta(minutes=1)}, "stale_feed"),
        ({"observed_at": datetime.now(timezone.utc) + timedelta(minutes=1)}, "future_feed"),
        ({"account_known": False}, "unknown_account"),
        ({"exposure_quote": Decimal("1001")}, "excess_exposure"),
        ({"quote_available": Decimal("0")}, "insufficient_quote"),
        ({"instrument_live": False}, "instrument_unavailable"),
    ],
)
def test_unsafe_observation_is_vetoed(change, reason):
    result = gate(observation=change)
    assert not result.approved
    assert reason in result.reasons


@pytest.mark.parametrize("label", ["REVIEW", "HALT"])
def test_laya_never_grants_permission(label):
    assert not gate(classification={"label": label}).approved


def test_abstention_blocks():
    assert not gate(classification={"abstained": True}).approved


@pytest.mark.parametrize("quantity", ["0", "-1", "0.000000001", "10", "0.000100001"])
def test_invalid_order_size_blocks(quantity):
    assert not gate(proposal={"quantity": Decimal(quantity)}).approved


@pytest.mark.parametrize(
    "flags,reason",
    [
        ({"source_mode": "LIVE"}, "live_forbidden"),
        ({"source_mode": "MARKET_ONLY"}, "execution_disabled"),
        ({"approval_available": False}, "approval_unavailable"),
        ({"unresolved": True}, "unresolved_prior_order"),
        ({"duplicate": True}, "duplicate_intent"),
    ],
)
def test_control_failures_block(flags, reason):
    from aegis.policy import check

    obs, laya, proposal, now = inputs()
    config = dict(source_mode="MOCK", approval_available=True, unresolved=False, duplicate=False)
    config.update(flags)
    result = check(obs, laya, proposal, now=now, **config)
    assert not result.approved
    assert reason in result.reasons


def test_no_trade_is_not_order_permission():
    assert not gate(proposal={"action": "NO_TRADE", "quantity": Decimal("0")}).approved


def test_unknown_symbol_and_insufficient_base_block():
    assert not gate(proposal={"symbol": "ETH-USDT"}).approved
    assert not gate(proposal={"action": "SELL", "quantity": Decimal("0.2")}).approved


@pytest.mark.parametrize("quantity", ["NaN", "Infinity", "-Infinity"])
def test_nonfinite_model_quantity_rejected(quantity):
    from aegis.models import Proposal

    with pytest.raises(ValidationError):
        Proposal(action="BUY", symbol="BTC-USDT", quantity=quantity, intent_id="x", summary="test")


def test_extra_tool_commands_rejected():
    from aegis.models import Proposal

    with pytest.raises(ValidationError):
        Proposal(
            action="BUY",
            symbol="BTC-USDT",
            quantity="0.1",
            intent_id="x",
            summary="test",
            tool="withdraw",
            risk_override=True,
        )


def test_gate_returns_an_exchange_tick_aligned_price_cap():
    result = gate()
    assert result.approved
    assert result.limit_price == Decimal("50101.1")
    assert result.limit_price % Decimal("0.1") == 0


def test_tick_rounding_and_fee_headroom_cannot_exceed_order_cap():
    result = gate(proposal={"quantity": Decimal("0.00049")}, observation={"tick_size": Decimal("1000")})
    assert not result.approved
    assert "excess_order_notional" in result.reasons


def test_exposure_cap_only_blocks_risk_increasing_buys():
    loaded = {"exposure_quote": Decimal("99549"), "base_available": Decimal("1")}
    assert "excess_exposure" in gate(observation=loaded).reasons
    assert gate(observation=loaded, proposal={"action": "SELL"}).approved
    assert gate(observation=loaded, max_exposure_quote=Decimal("200000")).approved


@pytest.mark.parametrize(
    "classification,approved",
    [
        ({"label": "REVIEW", "abstained": True, "confidence": 0}, True),
        ({"label": "CONTINUE", "confidence": 0.01}, True),
        ({"label": "HALT", "confidence": 0.01}, False),
    ],
)
def test_advisory_laya_only_vetoes_explicit_halt(classification, approved):
    assert gate(classification=classification, laya_advisory=True).approved is approved
    assert not gate(classification=classification).approved


def test_advisory_laya_never_applies_outside_demo_modes():
    from aegis.policy import check

    obs, laya, proposal, now = inputs()
    laya = laya.model_copy(update={"abstained": True})
    result = check(
        obs, laya, proposal, now=now, source_mode="LIVE", approval_available=True,
        unresolved=False, duplicate=False, laya_advisory=True,
    )
    assert "laya_not_clear" in result.reasons
