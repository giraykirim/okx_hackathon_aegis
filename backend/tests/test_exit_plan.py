"""Offline exit proposals: bounded by owned net inventory, separate from the entry edge gate."""

from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from test_policy import inputs
from test_position_lifecycle import BUY, PARTIAL, record

from aegis.store import Store


def proposal(store, **kwargs):
    from aegis.exit_plan import propose_exit_from_store

    return propose_exit_from_store(store, **kwargs)


def test_full_and_partial_exit_never_exceed_owned_net_inventory(tmp_path):
    store = Store(tmp_path / "exit.sqlite3", [])
    record(store, BUY)
    full = proposal(store, **fresh())
    assert (full.status, full.proposed_sell_btc, full.remaining_btc) == ("PROPOSE_CLOSE", "0.00019980", "0.00000000")
    half = proposal(store, fraction=Decimal("0.5"), **fresh())
    assert (half.status, half.proposed_sell_btc, half.remaining_btc) == ("PROPOSE_REDUCE", "0.00009990", "0.00009990")
    record(store, PARTIAL)
    after = proposal(store, **fresh())
    assert after.owned_net_btc == "0.00009990" and after.proposed_sell_btc == "0.00009990"
    store.close()


def test_dust_is_floored_to_lot_and_never_rounded_up(tmp_path):
    store = Store(tmp_path / "dust.sqlite3", [])
    record(store, ("b1", "buy", "0.0001", "100000", "-0.00000000123", "BTC", 0))
    out = proposal(store, **fresh())  # observed lot_size 0.00000001, min_size 0.00001
    assert out.owned_net_btc == "0.00009999877"
    assert out.sellable_btc == out.proposed_sell_btc == "0.00009999"
    assert out.remaining_btc == "0.00000000877"
    store.close()


def test_minimum_size_rules(tmp_path):
    store = Store(tmp_path / "min.sqlite3", [])
    record(store, ("b1", "buy", "0.000009", "100000", "0", "BTC", 0))
    assert proposal(store, **fresh()).status == "NO_EXIT" and "below_min_size" in proposal(store, **fresh()).reasons
    record(store, ("b2", "buy", "0.000016", "100000", "0", "BTC", 1))  # owned 0.000025
    tiny = proposal(store, fraction=Decimal("0.2"), **fresh())
    assert tiny.status == "NO_EXIT" and "reduction_below_min_size" in tiny.reasons
    rounded = proposal(store, fraction=Decimal("0.7"), **fresh())  # 0.0000175 would leave 0.0000075 < min size
    assert rounded.status == "PROPOSE_CLOSE" and rounded.proposed_sell_btc == "0.00002500"
    assert "remainder_below_min_size_full_close" in rounded.reasons
    with pytest.raises(ValueError):
        proposal(store, fraction=Decimal("0"), **fresh())
    store.close()


def test_unresolved_order_or_unknown_fee_routes_to_review(tmp_path):
    store = Store(tmp_path / "review.sqlite3", [])
    record(store, BUY)
    from aegis.models import Proposal

    pending = Proposal(action="SELL", symbol="BTC-USDT", quantity="0.0001", intent_id="p1", summary="t")
    assert store.claim(pending, "p" * 32, "OKX_DEMO")  # PENDING: inventory may still change
    out = proposal(store)
    assert out.status == "REVIEW" and "unresolved_prior_order" in out.reasons and out.proposed_sell_btc is None
    store.close()
    store = Store(tmp_path / "fee.sqlite3", [])
    record(store, BUY)
    record(store, ("s1", "sell", "0.0000999", "110000", None, "USDT", 10))
    out = proposal(store)
    assert out.status == "REVIEW" and "inventory_uncertain" in out.reasons and out.owned_net_btc is None
    store.close()


def test_preloaded_account_balance_and_entry_gate_do_not_enlarge_or_block_exit(tmp_path):
    store = Store(tmp_path / "gate.sqlite3", [])
    record(store, BUY)
    observation = inputs()[0].model_copy(update={"base_available": Decimal("1.5")})  # preloaded demo BTC
    out = proposal(store, observation=observation, now=observation.observed_at + timedelta(seconds=1))
    assert out.proposed_sell_btc == "0.00019980"  # owned only, never the 1.5 BTC account balance
    assert out.entry_edge_gate_applies is False and out.reference_bid == "49999"
    stale = proposal(store, observation=observation, now=observation.observed_at + timedelta(minutes=5))
    assert "stale_market_data" in stale.reasons and stale.status == "REVIEW" and stale.proposed_sell_btc is None
    store.close()


def owned_000025(tmp_path):
    store = Store(tmp_path / "constraints.sqlite3", [])
    record(store, ("b1", "buy", "0.000025", "100000", "0", "BTC", 0))
    return store


def fresh(**update):
    obs = inputs()[0].model_copy(update=update)
    return {"observation": obs, "now": obs.observed_at + timedelta(seconds=1)}


def test_observed_min_size_is_enforced_after_lot_rounding(tmp_path):
    store = owned_000025(tmp_path)
    out = proposal(store, **fresh(min_size=Decimal("0.0001")))
    assert out.status == "NO_EXIT" and "below_min_size" in out.reasons and out.proposed_sell_btc is None
    assert out.min_size == "0.0001"
    store.close()


def test_observed_lot_size_floors_the_proposed_quantity(tmp_path):
    store = owned_000025(tmp_path)
    out = proposal(store, **fresh(lot_size=Decimal("0.00001")))
    assert out.status == "PROPOSE_CLOSE" and out.proposed_sell_btc == "0.00002000"
    assert out.remaining_btc == "0.00000500" and out.lot_size == "0.00001"
    assert (Decimal(out.proposed_sell_btc) / Decimal("0.00001")) % 1 == 0
    store.close()


@pytest.mark.parametrize("kwargs,reason", [
    ({}, "no_market_data"),
    ({"stale": True}, "stale_market_data"),
    ({"symbol": "ETH-USDT"}, "symbol_mismatch"),
    ({"lot_size": Decimal("-1")}, "invalid_instrument_constraints"),
    ({"min_size": Decimal("0.000000005")}, "invalid_instrument_constraints"),  # below one lot
    ({"instrument_live": False}, "instrument_unavailable"),
])
def test_missing_stale_mismatched_or_invalid_market_data_gives_review(tmp_path, kwargs, reason):
    store = owned_000025(tmp_path)
    if not kwargs:
        out = proposal(store)
    else:
        obs = inputs()[0]
        if kwargs.get("stale"):
            call = {"observation": obs, "now": obs.observed_at + timedelta(minutes=5)}
        else:
            # model_construct bypasses validation to emulate a corrupt or foreign observation
            call = {"observation": obs.model_construct(**{**obs.model_dump(), **kwargs}),
                    "now": obs.observed_at + timedelta(seconds=1)}
        out = proposal(store, **call)
    assert out.status == "REVIEW" and reason in out.reasons
    assert out.proposed_sell_btc is None and out.sellable_btc is None
    store.close()


def test_exit_component_is_not_executable_and_only_wired_read_only():
    """Wiring is now allowed for the SHADOW assessment only (see test_exit_shadow.py for the
    behavioural fail-on-call proof); the module itself still has no route to an order adapter."""
    from aegis.exit_plan import ExitProposal
    from aegis.settings import Settings

    assert ExitProposal.model_fields["executable"].default is False
    assert ExitProposal.model_fields["order_adapter"].default is None
    root = Path(__file__).resolve().parents[1] / "aegis"
    source = (root / "exit_plan.py").read_text(encoding="utf-8")
    for forbidden in ("from .atk", "from .agent", "from .integrations", "place(", "reconcile(", "claim("):
        assert forbidden not in source
    for unwired in ("atk.py", "policy.py", "cost_gate.py", "store.py", "app.py"):
        text = (root / unwired).read_text(encoding="utf-8")
        assert ".exit_plan" not in text and "propose_exit" not in text  # never an execution/gate input
    defaults = Settings(_env_file=None)
    assert defaults.source_mode == "MARKET_ONLY" and not defaults.demo_enabled
    assert defaults.cost_taker_fee_rate is None
