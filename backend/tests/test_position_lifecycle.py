"""Buy -> partial sell -> full close on a temporary SQLite store (offline, synthetic fills only)."""

from datetime import timedelta
from decimal import Decimal

import pytest
from test_policy import inputs

from aegis.models import Proposal
from aegis.store import Store

T0 = 1792000000000


def own(store, ref, action="BUY", venue_order_id="default"):
    proposal = Proposal(action=action, symbol="BTC-USDT", quantity="0.0001", intent_id=ref, summary="t")
    client = ("c" + ref).ljust(32, "0")[:32]
    assert store.claim(proposal, client, "OKX_DEMO")
    store.order_status(ref, "VERIFIED", "ord-" + ref if venue_order_id == "default" else venue_order_id, "filled")
    return client


def fill(ref, client, side, qty, px, fee, fee_ccy, t, ord_id=None, **extra):
    return {"schema": 2, "ord_id": ord_id or "ord-" + ref, "cl_ord_id": client, "intent_id": ref,
            "decision_id": client, "side": side, "ord_type": "ioc", "avg_price": px, "filled_qty": qty,
            "fee": fee, "fee_ccy": fee_ccy, "rebate": "", "rebate_ccy": None,
            "fill_time_ms": str(T0 + t * 1000), "state": "filled", "source_mode": "OKX_DEMO", **extra}


def mark(store, price):
    observation = inputs()[0].model_copy(update={"price": Decimal(price), "bid": Decimal(price) - 1,
                                                 "ask": Decimal(price) + 1})
    store.save_mark(observation)
    return observation.observed_at + timedelta(seconds=1)


BUY = ("b1", "buy", "0.0002", "100000", "-0.0000002", "BTC", 0)
PARTIAL = ("s1", "sell", "0.0000999", "110000", "-0.010989", "USDT", 10)
CLOSE = ("s2", "sell", "0.0000999", "90000", "-0.008991", "USDT", 20)


def record(store, spec, **extra):
    ref, side, qty, px, fee, ccy, t = spec
    client = own(store, ref, "BUY" if side == "buy" else "SELL")
    store.record_fill(ref, fill(ref, client, side, qty, px, fee, ccy, t, **extra))
    return client


def test_buy_partial_sell_full_close_end_to_end(tmp_path):
    store = Store(tmp_path / "life.sqlite3", [])
    record(store, BUY)
    pnl = store.demo_pnl()
    assert pnl["inventory_qty"] == "0.00019980" and pnl["cost_basis"] == "20.00000000"
    assert pnl["valuation_status"] == "NO_MARK" and pnl["net"] is None and pnl["realized"] == "0.00000000"

    record(store, PARTIAL)
    at = mark(store, "120000")
    pnl = store.demo_pnl(now=at)
    assert pnl["inventory_qty"] == "0.00009990" and pnl["cost_basis"] == "10.00000000"
    assert pnl["realized"] == "0.97801100" and pnl["unrealized"] == "1.98800000"
    assert pnl["net"] == "2.96601100" and pnl["valuation_status"] == "CURRENT_MARK"

    record(store, CLOSE)
    pnl = store.demo_pnl(now=at)
    assert pnl["inventory_qty"] == "0.00000000" and pnl["valuation_status"] == "CLOSED_NO_MARK_NEEDED"
    # Gross price moves cancel (+0.999 / -0.999); only the fees remain, each counted once.
    assert pnl["realized"] == pnl["net"] == "-0.03998000"
    assert pnl["fees"] == "0.03998000"
    assert pnl["fee_breakdown"] == {"BTC": "-0.00000020", "USDT": "-0.01998000"}
    assert pnl["complete"] and pnl["fill_count"] == 3
    store.close()


def test_repeated_and_partial_reconciles_and_restart_never_double_count(tmp_path):
    path = tmp_path / "repeat.sqlite3"
    store = Store(path, [])
    record(store, BUY)
    ref, side, qty, px, fee, ccy, t = PARTIAL
    client = own(store, ref, "SELL")
    store.record_fill(ref, fill(ref, client, side, "0.00005", px, "-0.0055", ccy, t, state="partially_filled"))
    store.record_fill(ref, fill(ref, client, side, qty, px, fee, ccy, t))
    store.record_fill(ref, fill(ref, client, side, qty, px, fee, ccy, t))  # same read again
    store.record_fill(ref, fill(ref, client, side, "0.00005", px, "-0.0055", ccy, t))  # stale, smaller
    first = store.demo_pnl()
    store.close()
    reopened = Store(path, [])
    second = reopened.demo_pnl()
    for key in ("inventory_qty", "realized", "cost_basis", "fees", "fill_count"):
        assert first[key] == second[key]
    assert second["fill_count"] == 2 and second["inventory_qty"] == "0.00009990"
    reopened.close()


def test_out_of_order_records_follow_venue_fill_time(tmp_path):
    store = Store(tmp_path / "order.sqlite3", [])
    for spec in (CLOSE, BUY, PARTIAL):  # arrival order differs from execution order
        record(store, spec)
    pnl = store.demo_pnl()
    assert pnl["realized"] == "-0.03998000" and pnl["unmatched_sell_qty"] == "0.00000000"
    assert [row["ord_id"] for row in pnl["ledger"]] == ["ord-b1", "ord-s1", "ord-s2"]
    store.close()


def test_same_venue_order_under_two_intents_is_counted_once_and_flagged(tmp_path):
    store = Store(tmp_path / "dup.sqlite3", [])
    record(store, BUY)
    client = own(store, "b2", venue_order_id=None)  # second intent never learned its venue id
    store.record_fill("b2", fill("b2", client, "buy", "0.0002", "100000", "-0.0000002", "BTC", 0, ord_id="ord-b1"))
    pnl = store.demo_pnl()
    assert pnl["fill_count"] == 1
    assert any(i.startswith("duplicate_venue_order:ord-b1") for i in pnl["issues"])
    assert pnl["net"] is None and pnl["inventory_qty"] is None
    store.close()


def test_selling_more_than_owned_never_creates_negative_inventory(tmp_path):
    store = Store(tmp_path / "over.sqlite3", [])
    record(store, BUY)
    record(store, ("s9", "sell", "0.001", "110000", "-0.11", "USDT", 5))
    pnl = store.demo_pnl()
    assert pnl["inventory_qty"] == "0.00000000" and pnl["unmatched_sell_qty"] == "0.00080020"
    assert Decimal(pnl["realized"]) < Decimal("2.2")  # only the owned 0.0001998 BTC is attributed
    assert any(w.startswith("sell_exceeds_agent_inventory") for w in pnl["warnings"])
    store.close()


@pytest.mark.parametrize("fee,ccy,issue", [(None, "USDT", "missing_fee"), ("-0.01", "OKB", "unconverted_fee_currency")])
def test_unknown_sell_fee_withholds_every_accounting_figure(tmp_path, fee, ccy, issue):
    store = Store(tmp_path / "unknown.sqlite3", [])
    record(store, BUY)
    record(store, ("s1", "sell", "0.0000999", "110000", fee, ccy, 10))
    pnl = store.demo_pnl()
    assert any(i.startswith(issue) for i in pnl["issues"]) and not pnl["complete"]
    for key in ("realized", "unrealized", "net", "fees", "inventory_qty", "cost_basis"):
        assert pnl[key] is None, key
    assert pnl["valuation_status"] == "ACCOUNTING_INCOMPLETE"
    store.close()


@pytest.mark.parametrize("specs", [
    # Full sale plus a BTC fee: 0.0002 sold + 0.0000002 fee > 0.0002 owned.
    [("b1", "buy", "0.0002", "100000", "0", "BTC", 0), ("s1", "sell", "0.0002", "110000", "-0.0000002", "BTC", 10)],
    # Partial sale leaves 0.0000001 BTC; the later fee of 0.0000002 BTC exceeds it.
    [("b1", "buy", "0.0002", "100000", "0", "BTC", 0), ("s1", "sell", "0.0000999", "110000", "0", "BTC", 10),
     ("s2", "sell", "0.0001", "110000", "-0.0000002", "BTC", 20)],
])
def test_btc_sell_fee_beyond_owned_inventory_is_an_accounting_issue(tmp_path, specs):
    store = Store(tmp_path / "btcfee.sqlite3", [])
    for spec in specs:
        record(store, spec)
    pnl = store.demo_pnl()
    assert not pnl["complete"]
    assert any(i.startswith("base_fee_exceeds_inventory") for i in pnl["issues"])
    for key in ("realized", "net", "inventory_qty", "cost_basis", "fees"):
        assert pnl[key] is None, key
    assert pnl["valuation_status"] == "ACCOUNTING_INCOMPLETE"
    store.close()


def test_btc_sell_fee_within_inventory_is_accounted_once(tmp_path):
    store = Store(tmp_path / "btcfee_ok.sqlite3", [])
    record(store, ("b1", "buy", "0.0003", "100000", "0", "BTC", 0))
    record(store, ("s1", "sell", "0.0002", "110000", "-0.0000002", "BTC", 10))
    pnl = store.demo_pnl(now=mark(store, "110000"))
    # Independent cash view: -30 + 22 USDT, plus 0.0000998 BTC left worth 10.978 -> net 2.978.
    assert pnl["inventory_qty"] == "0.00009980" and pnl["cost_basis"] == "9.98000000"
    assert pnl["realized"] == "1.98000000" and pnl["unrealized"] == "0.99800000"
    assert pnl["net"] == "2.97800000" and pnl["complete"]
    assert pnl["fee_breakdown"] == {"BTC": "-0.00000020"} and pnl["fees"] == "0.02200000"
    store.close()


def test_odd_base_fee_dust_is_never_rounded_up(tmp_path):
    store = Store(tmp_path / "dust.sqlite3", [])
    record(store, ("b1", "buy", "0.0001", "100000", "-0.00000000123", "BTC", 0))
    pnl = store.demo_pnl()
    assert pnl["inventory_qty"] == "0.00009999877"  # 8-dp rounding would show 0.00010000 (more than owned)
    store.close()
