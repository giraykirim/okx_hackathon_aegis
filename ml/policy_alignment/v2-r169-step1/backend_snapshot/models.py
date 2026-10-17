from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

SourceMode = Literal["MOCK", "MARKET_ONLY", "OKX_DEMO"]
OrderStatus = Literal["NOT_SENT", "PENDING", "VERIFIED", "FAILED", "UNKNOWN"]
Money = Annotated[Decimal, Field(allow_inf_nan=False, max_digits=28, decimal_places=12)]
Positive = Annotated[Money, Field(gt=0)]
Nonnegative = Annotated[Money, Field(ge=0)]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return uuid4().hex


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Observation(StrictModel):
    symbol: Literal["BTC-USDT"]
    observed_at: AwareDatetime
    price: Positive
    ask: Positive
    bid: Positive
    min_size: Positive
    lot_size: Positive
    tick_size: Positive = Decimal("0.1")
    instrument_live: bool
    account_known: bool = False
    exposure_quote: Nonnegative = Decimal("0")
    quote_available: Nonnegative = Decimal("0")
    base_available: Nonnegative = Decimal("0")
    account_observed_at: AwareDatetime | None = None
    external_open_orders: bool = False


class Classification(StrictModel):
    label: Literal["CONTINUE", "REVIEW", "HALT"]
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    abstained: bool
    model_version: str = Field(min_length=1, max_length=128)
    latency_ms: float = Field(ge=0, allow_inf_nan=False)


class Proposal(StrictModel):
    action: Literal["NO_TRADE", "BUY", "SELL"]
    symbol: Literal["BTC-USDT"]
    quantity: Money
    intent_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    summary: str = Field(min_length=1, max_length=600)


class GateResult(StrictModel):
    approved: bool
    reasons: list[str]
    limit_price: Positive | None = None


class Event(StrictModel):
    id: str = Field(default_factory=new_id)
    timestamp: AwareDatetime = Field(default_factory=utcnow)
    run_id: str
    type: str
    severity: Literal["INFO", "WARNING", "ERROR"]
    actor: str
    message: str
    details: dict = Field(default_factory=dict)
    source_mode: SourceMode


class Decision(StrictModel):
    id: str = Field(default_factory=new_id)
    timestamp: AwareDatetime = Field(default_factory=utcnow)
    run_id: str
    symbol: Literal["BTC-USDT"]
    proposed_action: Literal["NO_TRADE", "BUY", "SELL"]
    laya_label: Literal["CONTINUE", "REVIEW", "HALT"]
    laya_confidence: float
    llm_summary: str
    evidence_ids: list[str]
    risk_approved: bool
    risk_reasons: list[str]
    execution_status: OrderStatus
    venue_order_id: str | None = None
    source_mode: SourceMode
    intent_id: str
    quantity: Money
    venue_state: str | None = None
    limit_price: Positive | None = None


class Capability(StrictModel):
    status: Literal["PASS", "FAIL", "NOT_TESTED"] = "NOT_TESTED"
    evidence: list[str] = Field(default_factory=list)
    checked_at: AwareDatetime | None = None


class Identity(StrictModel):
    chain_id: Literal[43113] = 43113
    registry_address: str | None = None
    agent_id: str | None = None
    agent_uri: str | None = None
    owner: str | None = None
    registration_tx_hash: str | None = None
    tx_hash: str | None = None
    verified: bool = False
    verification_checked_at: AwareDatetime | None = None
    verification_status: Literal["NOT_TESTED"] = "NOT_TESTED"
