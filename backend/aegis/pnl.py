"""Deterministic average-cost accounting of the agent's own venue-reported spot fills.

Field semantics follow OKX v5 "Get order details" (GET /api/v5/trade/order):
- ``accFillSz``/``avgPx`` are cumulative per order, so one record per order (upsert) cannot double count.
- ``fee`` is signed: negative = fee paid, positive = rebate. Spot buys are charged in the base
  currency, so a BTC fee changes BTC inventory rather than quote cash.
- ``rebate``/``rebateCcy`` is a separate, always-positive maker rebate ("" when none).
- ``fillTime`` is the venue's last fill time; reconcile wall-clock time is never an execution time.

Nothing is estimated: a missing fee, an unconvertible fee currency or a missing mark makes the
affected figure ``None`` and is listed in ``issues`` instead of being treated as zero.
"""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

QUANTUM = Decimal("0.00000001")
ZERO = Decimal("0")


def _decimal(value) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() else None


def money(value: Decimal | None) -> str | None:
    return None if value is None else format(value.quantize(QUANTUM), "f")


def fill_sort_key(fill: dict) -> tuple:
    """Venue execution time first; legacy records fall back to their stored timestamp."""
    time_ms = _decimal(fill.get("fill_time_ms")) or _decimal(fill.get("u_time_ms"))
    if time_ms is not None:
        when = datetime.fromtimestamp(int(time_ms) / 1000, timezone.utc).isoformat()
    else:
        when = fill.get("filled_at") or fill.get("recorded_at") or ""
    return (when, str(fill.get("ord_id") or ""), str(fill.get("intent_id") or ""))


def fill_time_source(fill: dict) -> str:
    if _decimal(fill.get("fill_time_ms")) is not None:
        return "venue_fillTime"
    if _decimal(fill.get("u_time_ms")) is not None:
        return "venue_uTime"
    return "reconcile_time_legacy"


def quantity(value: Decimal | None) -> str | None:
    """Base-currency amounts are never rounded: exact digits beyond 8 dp are kept (no rounding up)."""
    if value is None:
        return None
    if value == value.quantize(QUANTUM):
        return money(value)
    return format(value.normalize(), "f")


def ledger(fills: list[dict], symbol: str) -> dict:
    """Exact average-cost state (Decimals) after replaying the fills in venue-time order."""
    base, quote = symbol.split("-")
    qty, cost, realized = ZERO, ZERO, ZERO
    fee_value_quote = ZERO  # signed: negative = net cost, valued at each fill's own price
    fee_native: dict[str, Decimal] = {}
    unmatched_sell = ZERO
    issues: list[str] = []
    warnings: list[str] = []
    rows = []
    counted = 0
    seen_orders: set[str] = set()
    for fill in sorted(fills, key=fill_sort_key):
        ref = str(fill.get("ord_id") or fill.get("intent_id") or "?")
        if fill.get("ord_id"):
            if fill["ord_id"] in seen_orders:
                # One venue order can only execute once; a second record is a data error, not a fill.
                issues.append(f"duplicate_venue_order:{fill['ord_id']}")
                continue
            seen_orders.add(fill["ord_id"])
        side = str(fill.get("side") or "").lower()
        filled = _decimal(fill.get("filled_qty"))
        price = _decimal(fill.get("avg_price"))
        if side not in {"buy", "sell"} or filled is None or filled < 0:
            issues.append(f"invalid_fill:{ref}")
            continue
        if filled == 0:
            continue  # canceled IOC without execution
        if price is None or price <= 0:
            issues.append(f"invalid_fill_price:{ref}")
            continue
        counted += 1
        source = fill_time_source(fill)
        if source == "reconcile_time_legacy":
            warnings.append(f"fill_time_unverified:{ref}")
        if fill.get("schema") != 2:
            warnings.append(f"legacy_record_rebate_not_captured:{ref}")

        amounts: list[tuple[Decimal, str]] = []
        fee = _decimal(fill.get("fee"))
        if fee is None:
            issues.append(f"missing_fee:{ref}")
        elif fee != 0:
            ccy = str(fill.get("fee_ccy") or "").upper()
            if not ccy:
                issues.append(f"missing_fee_currency:{ref}")
            else:
                amounts.append((fee, ccy))
        rebate = _decimal(fill.get("rebate"))
        if fill.get("rebate") not in (None, "") and rebate is None:
            issues.append(f"invalid_rebate:{ref}")
        if rebate:
            if side == "sell" and str(fill.get("ord_type") or "").lower() != "ioc":
                # OKX reports maker-sell fee and rebate as overlapping totals in two currencies.
                issues.append(f"ambiguous_maker_sell_fee:{ref}")
            else:
                ccy = str(fill.get("rebate_ccy") or "").upper()
                if not ccy:
                    issues.append(f"missing_rebate_currency:{ref}")
                else:
                    amounts.append((rebate, ccy))
        base_adj, quote_adj = ZERO, ZERO
        for amount, ccy in amounts:
            fee_native[ccy] = fee_native.get(ccy, ZERO) + amount
            if ccy == base:
                base_adj += amount
            elif ccy == quote:
                quote_adj += amount
            else:
                issues.append(f"unconverted_fee_currency:{ccy}:{ref}")

        if side == "buy":
            # Quote fees are capitalized into cost; base fees change the units received.
            qty += filled + base_adj
            cost += filled * price - quote_adj
            fee_value_quote += quote_adj + base_adj * price
        else:
            matched = min(filled, qty)
            if matched < filled:
                # Units beyond the agent's own inventory (e.g. preloaded demo assets) are not its profit.
                unmatched_sell += filled - matched
                warnings.append(f"sell_exceeds_agent_inventory:{ref}")
            if matched > 0:
                share = matched / filled
                removed = cost * matched / qty
                realized += matched * price + quote_adj * share - removed
                cost -= removed
                qty -= matched
                fee_value_quote += (quote_adj + base_adj * price) * share
                base_part = base_adj * share
                if base_part < 0:
                    # Sold units plus a BTC fee must both come from verified inventory; a fee that
                    # exceeds what remains has an unverifiable source and is never dropped or clipped.
                    if -base_part > qty:
                        issues.append(f"base_fee_exceeds_inventory:{ref}")
                    else:
                        removed = cost * -base_part / qty
                        realized -= removed
                        cost -= removed
                        qty += base_part
                elif base_part > 0:
                    qty += base_part
        if qty < 0:
            issues.append(f"negative_inventory:{ref}")
            qty = ZERO
        if qty == 0 and cost != 0:
            # Capitalized fees of a fully closed position are realized, never left behind.
            realized -= cost
            cost = ZERO
        rows.append(
            {
                "ord_id": fill.get("ord_id"),
                "intent_id": fill.get("intent_id"),
                "side": side,
                "filled_qty": quantity(filled),
                "avg_price": money(price),
                "fee": fill.get("fee"),
                "fee_ccy": fill.get("fee_ccy"),
                "rebate": fill.get("rebate"),
                "rebate_ccy": fill.get("rebate_ccy"),
                "fill_time_source": source,
                "ordered_at": fill_sort_key(fill)[0] or None,
                "inventory_after": quantity(qty),
            }
        )
    return {
        "qty": qty,
        "cost": cost,
        "realized": realized,
        "fee_value_quote": fee_value_quote,
        "fee_native": fee_native,
        "unmatched_sell": unmatched_sell,
        "counted": counted,
        # Any issue means the inventory/cost/realized replay may be wrong, so none of it is trusted.
        "accounting_complete": not issues,
        "issues": issues,
        "warnings": warnings,
        "rows": rows,
    }


def compute(fills: list[dict], symbol: str, mark_price: Decimal | None) -> dict:
    """Average-cost realized/unrealized/net for one spot symbol (e.g. ``BTC-USDT``).

    A missing mark only withholds unrealized/net. Any accounting issue (missing or unconvertible
    fee, duplicate venue order, invalid fill) withholds every accounting figure instead of
    reporting a value computed without the unknown part.
    """
    state = ledger(fills, symbol)
    qty, cost, realized = state["qty"], state["cost"], state["realized"]
    issues = list(state["issues"])
    trusted = state["accounting_complete"]
    if qty == 0:
        unrealized = ZERO  # a closed position needs no mark
    elif mark_price is None:
        unrealized = None
        issues.append("mark_price_missing")
    else:
        unrealized = qty * mark_price - cost
    complete = not issues
    net = realized + unrealized if complete and unrealized is not None else None
    return {
        "realized": money(realized) if trusted else None,
        "unrealized": money(unrealized) if trusted else None,
        "net": money(net),
        # Positive = cost to the agent, negative = net rebate; informational only, already inside
        # cost basis/proceeds and therefore never subtracted from net a second time.
        "fees": money(-state["fee_value_quote"]) if trusted else None,
        "fee_breakdown": {ccy: money(value) for ccy, value in sorted(state["fee_native"].items())},
        "inventory_qty": quantity(qty) if trusted else None,
        "cost_basis": money(cost) if trusted else None,
        "average_cost": money(cost / qty) if trusted and qty > 0 else None,
        "fill_count": state["counted"],
        "unmatched_sell_qty": quantity(state["unmatched_sell"]),
        "complete": complete,
        "issues": issues,
        "warnings": state["warnings"],
        "ledger": state["rows"],
    }
