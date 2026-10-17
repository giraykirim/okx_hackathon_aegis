from datetime import datetime
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

from .models import Classification, GateResult, Observation, Proposal


def check(
    observation: Observation,
    classification: Classification,
    proposal: Proposal,
    *,
    now: datetime,
    source_mode: str,
    approval_available: bool,
    unresolved: bool,
    duplicate: bool,
    run_reserved_notional: Decimal = Decimal("0"),
    run_order_count: int = 0,
    max_run_notional: Decimal = Decimal("25"),
    max_run_orders: int = 1,
) -> GateResult:
    """Final authority. Operational CONTINUE is only one prerequisite."""
    reasons = []
    if proposal.symbol != "BTC-USDT" or observation.symbol != "BTC-USDT":
        reasons.append("symbol_not_allowed")
    try:
        observation = Observation.model_validate(observation.model_dump())
        classification = Classification.model_validate(classification.model_dump())
        proposal = Proposal.model_validate(proposal.model_dump())
    except (ValueError, TypeError):
        return GateResult(approved=False, reasons=reasons + ["corrupt_data"])
    age = (now - observation.observed_at).total_seconds()
    if source_mode not in {"MOCK", "MARKET_ONLY", "OKX_DEMO"}:
        reasons.append("live_forbidden")
    if source_mode == "MARKET_ONLY":
        reasons.append("execution_disabled")
    if not approval_available:
        reasons.append("approval_unavailable")
    if unresolved or observation.external_open_orders:
        reasons.append("unresolved_prior_order")
    if duplicate:
        reasons.append("duplicate_intent")
    if age > 15:
        reasons.append("stale_feed")
    if age < -2:
        reasons.append("future_feed")
    if not observation.instrument_live:
        reasons.append("instrument_unavailable")
    if not observation.account_known:
        reasons.append("unknown_account")
    if observation.account_observed_at is not None:
        account_age = (now - observation.account_observed_at).total_seconds()
        if not -2 <= account_age <= 15:
            reasons.append("stale_account")
    elif source_mode == "OKX_DEMO":
        reasons.append("unknown_account_timestamp")
    if classification.label != "CONTINUE" or classification.abstained or classification.confidence < 0.8:
        reasons.append("laya_not_clear")
    if proposal.action == "NO_TRADE":
        reasons.append("no_trade_proposed")
    if proposal.symbol != observation.symbol:
        reasons.append("symbol_not_allowed")
    quantity = proposal.quantity
    limit_price = None
    valid = quantity.is_finite() and quantity > 0
    if not valid or quantity < observation.min_size or quantity % observation.lot_size != 0:
        reasons.append("invalid_quantity")
    if valid:
        # Bind the venue's IOC execution price, then reserve an additional 1% fee allowance.
        if proposal.action == "SELL":
            raw_price = min(observation.bid, observation.price) * Decimal("0.99")
            rounding = ROUND_FLOOR
        else:
            raw_price = max(observation.ask, observation.price) * Decimal("1.01")
            rounding = ROUND_CEILING
        limit_price = (raw_price / observation.tick_size).to_integral_value(
            rounding=rounding
        ) * observation.tick_size
        if limit_price <= 0:
            reasons.append("invalid_execution_price")
            limit_price = None
        # For sells, bound marked exposure/notional using the current high reference as well.
        notional = (
            quantity * max(limit_price or raw_price, observation.ask, observation.price) * Decimal("1.01")
        )
        if notional > 25:
            reasons.append("excess_order_notional")
        if run_order_count >= max_run_orders or run_reserved_notional + notional > max_run_notional:
            reasons.append("run_budget_exhausted")
        projected = observation.exposure_quote + (notional if proposal.action == "BUY" else Decimal("0"))
        if projected > 1000:
            reasons.append("excess_exposure")
        if proposal.action == "BUY" and notional > observation.quote_available:
            reasons.append("insufficient_quote")
        if proposal.action == "SELL" and quantity > observation.base_available:
            reasons.append("insufficient_base")
    if observation.bid > observation.ask:
        reasons.append("crossed_quotes")
    return GateResult(approved=not reasons, reasons=reasons, limit_price=limit_price)
