from typing import Literal

from pydantic import AwareDatetime, Field

from .models import Classification, Positive, StrictModel


class RiskRequest(StrictModel):
    symbol: Literal["BTC-USDT"]
    action: Literal["BUY", "SELL"]
    quantity: Positive
    client_request_id: str | None = Field(default=None, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")


class ATKReceipt(StrictModel):
    id: str
    toolkit: Literal["@okx_ai/okx-trade-cli@1.4.8"] = "@okx_ai/okx-trade-cli@1.4.8"
    operation: Literal["ticker", "instruments"]
    command: list[str]
    site: str
    requested_at: AwareDatetime
    completed_at: AwareDatetime
    market_timestamp: AwareDatetime | None
    source_mode: Literal["MARKET_ONLY", "OKX_DEMO"]
    run_id: str
    status: Literal["PASS", "FAIL"]
    result_sha256: str | None
    stdout_sha256: str | None
    elapsed_ms: float
    error_type: str | None = None


class MarketProvenance(StrictModel):
    status: Literal["PASS", "FAIL", "UNAVAILABLE"]
    source: Literal["OFFICIAL_OKX_ATK"] = "OFFICIAL_OKX_ATK"
    site: str
    market_timestamp: AwareDatetime | None
    receipts: list[ATKReceipt]


class MarketChecks(StrictModel):
    status: Literal["PASS", "FAIL", "UNAVAILABLE"]
    reasons: list[str]
    policy_limit_price: Positive | None


class RiskAssessment(StrictModel):
    assessment_id: str
    timestamp: AwareDatetime
    run_id: str
    request: RiskRequest
    source_mode: Literal["MARKET_ONLY"] = "MARKET_ONLY"
    assessment: Literal["REVIEW", "HALT"]
    reasons: list[str]
    execution_authority: Literal[False] = False
    order_permission: Literal[False] = False
    account_provenance: Literal["UNAVAILABLE"] = "UNAVAILABLE"
    market_provenance: MarketProvenance
    market_checks: MarketChecks
    classification: Classification
    laya_status: Literal["AVAILABLE", "UNAVAILABLE"]
    evren_status: Literal["AVAILABLE", "FALLBACK"]
    analysis_summary: str
    limitations: list[str]
    evidence_ids: list[str]
    assessment_sha256: str


class ServiceAuth(StrictModel):
    scheme: Literal["api_key"] = "api_key"
    header: Literal["X-AEGIS-Key"] = "X-AEGIS-Key"
    required: Literal[True] = True
    configured: bool
    requests_per_minute: int
    concurrent_assessments: Literal[1] = 1
    max_request_bytes: Literal[2048] = 2048
    scope: Literal["single deployment credential; single worker"] = (
        "single deployment credential; single worker"
    )


class ProposedPricing(StrictModel):
    status: Literal["PROPOSED_NOT_BILLED"] = "PROPOSED_NOT_BILLED"
    currency: Literal["USD"] = "USD"
    per_assessment: str = "0.01"
    b2b_monthly: str = "99"
    included_assessments: int = 10000
    payment_integration: Literal["NOT_IMPLEMENTED"] = "NOT_IMPLEMENTED"


class MarketplaceStatus(StrictModel):
    listing_status: Literal["NOT_LISTED"] = "NOT_LISTED"
    integration_feasibility: Literal["POSSIBLE"] = "POSSIBLE"
    verified_listing_url: None = None
    requirements_url: str = "https://web3.okx.com/onchainos/dev-docs/okxai/asp-introduction"


class ServiceInfo(StrictModel):
    name: Literal["AEGIS Risk Check Service"] = "AEGIS Risk Check Service"
    version: Literal["1.0.0"] = "1.0.0"
    purpose: str = "Operational pre-trade assessment and monitoring for trading-agent developers"
    target_customer: str = "Teams building agentic trading applications and agent-platform operators"
    execution_authority: Literal[False] = False
    public_url: None = None
    deployment_status: Literal["PUBLIC_NOT_VERIFIED"] = "PUBLIC_NOT_VERIFIED"
    evaluate_path: Literal["/api/v1/risk/evaluate"] = "/api/v1/risk/evaluate"
    auth: ServiceAuth
    pricing: ProposedPricing = Field(default_factory=ProposedPricing)
    okx_ai: MarketplaceStatus = Field(default_factory=MarketplaceStatus)
    limitations: list[str]
