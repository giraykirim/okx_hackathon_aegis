"""Pre-trade cost gate: a trade needs a measured edge that survives a full round trip.

It complements ``policy.check`` and can only add vetoes. Round trip for a horizon ``H``:

    BUY : enter at ask*(1+s), exit at E[mid_H]-half_spread at the bid side, *(1-s)
    SELL: enter at bid*(1-s), exit (buy back) at E[mid_H]+half_spread at the ask side, *(1+s)
    E[mid_H] = mid * (1 +/- edge_bps/1e4) in the trade direction

    price_result = qty * signed(exit_px - entry_px)        # spread and slippage live in prices only
    fees         = taker_fee * qty * (entry_px + exit_px)  # both legs taker; maker fill never assumed
    margin       = qty * entry_px * (edge_uncertainty_bps + config_uncertainty_bps) / 1e4
    net          = price_result - fees - margin            # approved only if net/notional > min bps

A model's direction or confidence is not an edge. Without a measured, out-of-sample validated
estimate, a known fee, an exit plan, fresh data and visible liquidity the verdict is REVIEW or
NO_TRADE; no figure is invented to let an order through.
"""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, Field

from .models import Money, Observation, Proposal, StrictModel

BPS = Decimal("10000")
QUANTUM = Decimal("0.00000001")
# Inputs that are absent rather than unfavourable route to human REVIEW.
REVIEW_REASONS = {
    "cost_edge_source_missing",
    "cost_edge_unverified",
    "cost_exit_plan_missing",
    "cost_unknown_fee",
    "cost_liquidity_unknown",
}


class EdgeEstimate(StrictModel):
    """Expected mid-price move in the trade's direction, measured on held-out data."""

    expected_return_bps: Money
    uncertainty_bps: Money = Field(ge=0)
    horizon_seconds: int = Field(gt=0)
    source: str = Field(min_length=1, max_length=200)
    out_of_sample_validated: bool
    sample_size: int = Field(ge=0)
    as_of: AwareDatetime


class ExitPlan(StrictModel):
    method: Literal["TAKER_IOC_AT_HORIZON"] = "TAKER_IOC_AT_HORIZON"
    horizon_seconds: int = Field(gt=0)


class CostConfig(StrictModel):
    taker_fee_rate: Money | None = None
    fee_source: str = "NOT_CONFIGURED"
    slippage_bps_per_leg: Money = Field(ge=0)
    uncertainty_bps: Money = Field(ge=0)
    max_data_age_seconds: float = Field(gt=0)
    max_spread_bps: Money = Field(ge=0)
    min_net_edge_bps: Money = Field(ge=0)

    @classmethod
    def from_settings(cls, settings) -> "CostConfig":
        return cls(
            taker_fee_rate=settings.cost_taker_fee_rate,
            fee_source="settings:AEGIS_COST_TAKER_FEE_RATE"
            if settings.cost_taker_fee_rate is not None
            else "NOT_CONFIGURED",
            slippage_bps_per_leg=settings.cost_slippage_bps_per_leg,
            uncertainty_bps=settings.cost_uncertainty_bps,
            max_data_age_seconds=settings.cost_max_data_age_seconds,
            max_spread_bps=settings.cost_max_spread_bps,
            min_net_edge_bps=settings.cost_min_net_edge_bps,
        )


class CostAssessment(StrictModel):
    status: Literal["APPROVED", "NO_TRADE", "REVIEW", "NOT_APPLICABLE"]
    approved: bool
    reasons: list[str]
    explanation: str
    inputs: dict
    breakdown: dict | None = None


def _q(value: Decimal) -> str:
    return format(value.quantize(QUANTUM), "f")


def evaluate(
    observation: Observation,
    proposal: Proposal,
    *,
    now: datetime,
    config: CostConfig,
    edge: EdgeEstimate | None,
    exit_plan: ExitPlan | None,
    top_of_book: dict | None,
) -> CostAssessment:
    inputs = {
        "action": proposal.action,
        "quantity": format(proposal.quantity, "f"),
        "bid": format(observation.bid, "f"),
        "ask": format(observation.ask, "f"),
        "market_observed_at": observation.observed_at.isoformat(),
        "market_data_age_seconds": round((now - observation.observed_at).total_seconds(), 3),
        "top_of_book": top_of_book,
        "taker_fee_rate": None if config.taker_fee_rate is None else format(config.taker_fee_rate, "f"),
        "fee_source": config.fee_source,
        "edge": None if edge is None else edge.model_dump(mode="json"),
        "exit_plan": None if exit_plan is None else exit_plan.model_dump(mode="json"),
        "config": config.model_dump(mode="json"),
    }
    if proposal.action == "NO_TRADE":
        return CostAssessment(
            status="NOT_APPLICABLE",
            approved=False,
            reasons=[],
            explanation="No order proposed; nothing to cost.",
            inputs=inputs,
        )

    reasons: list[str] = []
    qty = proposal.quantity
    buy = proposal.action == "BUY"
    if edge is None:
        reasons.append("cost_edge_source_missing")
    elif not edge.out_of_sample_validated:
        reasons.append("cost_edge_unverified")
    if exit_plan is None or (edge is not None and exit_plan.horizon_seconds != edge.horizon_seconds):
        reasons.append("cost_exit_plan_missing")
    if config.taker_fee_rate is None:
        reasons.append("cost_unknown_fee")
    age = (now - observation.observed_at).total_seconds()
    if not -2 <= age <= config.max_data_age_seconds:
        reasons.append("cost_stale_data")
    if edge is not None and (now - edge.as_of).total_seconds() > config.max_data_age_seconds:
        reasons.append("cost_stale_edge")

    size_key = "ask_sz" if buy else "bid_sz"
    available = None
    if top_of_book and top_of_book.get(size_key) not in (None, ""):
        try:
            available = Decimal(str(top_of_book[size_key]))
        except ArithmeticError:
            available = None
    if available is None:
        reasons.append("cost_liquidity_unknown")
    elif qty > available:
        # Deeper levels are not observed, so their prices cannot be assumed.
        reasons.append("cost_insufficient_liquidity")

    bid, ask = observation.bid, observation.ask
    mid = (bid + ask) / 2
    spread_bps = (ask - bid) / mid * BPS
    if spread_bps > config.max_spread_bps:
        reasons.append("cost_excess_spread")

    breakdown = None
    if edge is not None and config.taker_fee_rate is not None:
        slip = config.slippage_bps_per_leg / BPS
        half = (ask - bid) / 2
        move = edge.expected_return_bps / BPS
        if buy:
            entry_touch, exit_touch = ask, mid * (1 + move) - half
            entry_px, exit_px = entry_touch * (1 + slip), exit_touch * (1 - slip)
            price_result = qty * (exit_px - entry_px)
        else:
            entry_touch, exit_touch = bid, mid * (1 - move) + half
            entry_px, exit_px = entry_touch * (1 - slip), exit_touch * (1 + slip)
            price_result = qty * (entry_px - exit_px)
        slippage = qty * (abs(entry_px - entry_touch) + abs(exit_px - exit_touch))
        notional = qty * entry_px
        fees = config.taker_fee_rate * qty * (entry_px + exit_px)
        margin = notional * (edge.uncertainty_bps + config.uncertainty_bps) / BPS
        gross_edge = qty * mid * move
        net = price_result - fees - margin
        net_bps = net / notional * BPS
        breakdown = {
            "horizon_seconds": edge.horizon_seconds,
            "exit_assumption": "taker IOC at horizon on the opposite side of the book",
            "mid": _q(mid),
            "spread_bps": _q(spread_bps),
            "entry_price": _q(entry_px),
            "expected_exit_price": _q(exit_px),
            "entry_notional": _q(notional),
            "expected_gross_edge": _q(gross_edge),
            "spread_cost_in_prices": _q(qty * (ask - bid)),
            "slippage_cost_in_prices": _q(slippage),
            "price_result_after_spread_and_slippage": _q(price_result),
            "entry_fee": _q(config.taker_fee_rate * qty * entry_px),
            "exit_fee": _q(config.taker_fee_rate * qty * exit_px),
            "uncertainty_margin": _q(margin),
            "expected_net_after_costs": _q(price_result - fees),
            "expected_net_after_margin": _q(net),
            "expected_net_after_margin_bps": _q(net_bps),
            "required_min_net_bps": _q(config.min_net_edge_bps),
        }
        if net_bps <= config.min_net_edge_bps:
            reasons.append("cost_insufficient_edge")

    approved = not reasons
    status = "APPROVED" if approved else "REVIEW" if set(reasons) & REVIEW_REASONS else "NO_TRADE"
    if approved:
        explanation = (
            f"Expected net {breakdown['expected_net_after_margin_bps']} bps after fees, spread, "
            f"slippage and uncertainty exceeds the {breakdown['required_min_net_bps']} bps minimum."
        )
    elif breakdown is not None:
        explanation = (
            f"Blocked ({', '.join(reasons)}); expected net after margin "
            f"{breakdown['expected_net_after_margin_bps']} bps vs required "
            f"{breakdown['required_min_net_bps']} bps."
        )
    else:
        explanation = f"Blocked ({', '.join(reasons)}); expected advantage cannot be measured."
    return CostAssessment(
        status=status,
        approved=approved,
        reasons=reasons,
        explanation=explanation,
        inputs=inputs,
        breakdown=breakdown,
    )
