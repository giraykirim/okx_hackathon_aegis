"""Offline position-reduction proposals for the agent's own spot inventory.

A proposal is advisory data only: it is never routed to an exchange adapter and is not called
by the agent cycle. Reduction rules are deliberately separate from the entry cost gate: reducing
owned inventory needs no measured edge, but it must never sell more than the agent verifiably
owns (preloaded demo balances are not the agent's), and it is withheld when the inventory itself
is uncertain (accounting issues or an unresolved order).
"""

from datetime import datetime
from decimal import ROUND_FLOOR, Decimal
from typing import Literal

from .models import Observation, StrictModel, utcnow
from .pnl import ledger, quantity

MAX_MARKET_AGE_SECONDS = 15


class ExitProposal(StrictModel):
    status: Literal["PROPOSE_REDUCE", "PROPOSE_CLOSE", "NO_EXIT", "REVIEW"]
    reasons: list[str]
    rule_set: Literal["position_reduction_v1"] = "position_reduction_v1"
    entry_edge_gate_applies: Literal[False] = False
    executable: Literal[False] = False
    order_adapter: None = None
    requested_fraction: str
    owned_net_btc: str | None = None
    sellable_btc: str | None = None
    proposed_sell_btc: str | None = None
    remaining_btc: str | None = None
    # Instrument constraints come only from the supplied observation; never assumed defaults.
    lot_size: str | None = None
    min_size: str | None = None
    reference_bid: str | None = None
    market_observed_at: datetime | None = None
    market_age_seconds: float | None = None
    explanation: str


def floor_lot(amount: Decimal, lot: Decimal) -> Decimal:
    return (amount / lot).to_integral_value(rounding=ROUND_FLOOR) * lot


def market_problem(observation: Observation | None, now: datetime, symbol: str) -> str | None:
    """Why the observation cannot supply current, valid instrument constraints (None if it can)."""
    if observation is None:
        return "no_market_data"
    if observation.symbol != symbol:
        return "symbol_mismatch"
    age = (now - observation.observed_at).total_seconds()
    if not -2 <= age <= MAX_MARKET_AGE_SECONDS:
        return "stale_market_data"
    lot, minimum = observation.lot_size, observation.min_size
    valid = all(isinstance(v, Decimal) and v.is_finite() and v > 0 for v in (lot, minimum))
    if not valid or minimum < lot:
        return "invalid_instrument_constraints"
    if not observation.instrument_live:
        return "instrument_unavailable"
    return None


def propose_exit(
    fills: list[dict],
    *,
    unresolved_orders: bool,
    fraction: Decimal = Decimal(1),
    observation: Observation | None = None,
    now: datetime | None = None,
    symbol: str = "BTC-USDT",
) -> ExitProposal:
    fraction = Decimal(fraction)
    if not 0 < fraction <= 1:
        raise ValueError("fraction must be in (0, 1]")
    base = {"requested_fraction": format(fraction, "f")}
    reasons: list[str] = []
    now = now or utcnow()
    if observation is not None:
        base.update(reference_bid=format(observation.bid, "f"), market_observed_at=observation.observed_at,
                    market_age_seconds=round((now - observation.observed_at).total_seconds(), 3))

    state = ledger(fills, symbol)
    if not state["accounting_complete"]:
        return ExitProposal(status="REVIEW", reasons=["inventory_uncertain", *state["issues"]],
                            explanation="Owned inventory cannot be established from the recorded fills.", **base)
    owned = state["qty"]
    base["owned_net_btc"] = quantity(owned)
    if unresolved_orders:
        return ExitProposal(status="REVIEW", reasons=["unresolved_prior_order"],
                            explanation="An unresolved order may still change the owned inventory.", **base)
    if owned <= 0:
        return ExitProposal(status="NO_EXIT", reasons=["no_owned_inventory"],
                            explanation="The agent owns no verified inventory.", **base)
    problem = market_problem(observation, now, symbol)
    if problem:
        return ExitProposal(status="REVIEW", reasons=[problem],
                            explanation="No current, valid instrument constraints; no sell quantity proposed.", **base)
    lot, minimum = observation.lot_size, observation.min_size
    base.update(lot_size=format(lot, "f"), min_size=format(minimum, "f"))
    sellable = floor_lot(owned, lot)
    if sellable < minimum:
        return ExitProposal(status="NO_EXIT", reasons=["below_min_size"], remaining_btc=quantity(owned),
                            explanation="Owned inventory rounded to the lot size is below the minimum size.", **base)
    base["sellable_btc"] = quantity(sellable)
    proposed = floor_lot(sellable * fraction, lot)
    if proposed < minimum:
        return ExitProposal(status="NO_EXIT", reasons=["reduction_below_min_size"],
                            explanation="The requested reduction is below the exchange minimum size.", **base)
    if 0 < sellable - proposed < minimum:
        proposed = sellable
        reasons.insert(0, "remainder_below_min_size_full_close")
    status = "PROPOSE_CLOSE" if proposed == sellable else "PROPOSE_REDUCE"
    return ExitProposal(
        status=status,
        reasons=reasons,
        proposed_sell_btc=quantity(proposed),
        remaining_btc=quantity(owned - proposed),
        explanation=f"Advisory only: sell {quantity(proposed)} of {quantity(owned)} owned BTC; "
        "not executable and not routed to any order adapter.",
        **base,
    )


def propose_exit_from_store(store, **kwargs) -> ExitProposal:
    """Proposal from the agent-owned fills and unresolved demo intents of a ``Store`` (read-only)."""
    fills, _ = store.owned_demo_fills()
    unresolved = any(row["source_mode"] == "OKX_DEMO" for row in store.unresolved())
    return propose_exit(fills, unresolved_orders=unresolved, **kwargs)
