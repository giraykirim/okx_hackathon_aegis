import re
from decimal import Decimal
from typing import Any, Literal

from pydantic import AwareDatetime, Field, field_validator, model_validator

from .models import Classification, Positive, StrictModel


class RiskRequest(StrictModel):
    symbol: Literal["BTC-USDT"]
    action: Literal["BUY", "SELL"]
    quantity: Positive
    client_request_id: str | None = Field(default=None, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")


class RiskEvaluationRequest(StrictModel):
    request_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    symbol: Literal["BTC-USDT"]
    proposed_action: Literal["BUY", "SELL", "NO_TRADE"]
    proposed_notional: str = Field(max_length=32, pattern=r"^(0|[1-9][0-9]*)(\.[0-9]{1,12})?$")
    requester_context: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_notional(self):
        value = Decimal(self.proposed_notional)
        if value > Decimal("1000000000000000"):
            raise ValueError("Notional exceeds input bounds")
        if value == 0 and self.proposed_action != "NO_TRADE":
            raise ValueError("Trading notional must be positive")
        return self

    @field_validator("requester_context")
    @classmethod
    def reject_private_context(cls, context):
        def visit(value, depth=0):
            if depth > 8:
                raise ValueError("Requester context exceeds nesting limit")
            if isinstance(value, dict):
                for key, item in value.items():
                    if re.search(
                        r"balance|credential|secret|token|mnemonic|passphrase|private.?key|api.?key|authorization",
                        key,
                        re.I,
                    ):
                        raise ValueError("Requester context must not contain credentials or private balances")
                    visit(item, depth + 1)
            elif isinstance(value, list):
                for item in value:
                    visit(item, depth + 1)

        visit(context)
        return context


class VerifiedChainReceipt(StrictModel):
    chain_id: Literal[43113]
    contract_address: str = Field(pattern=r"^0x[a-fA-F0-9]{40}$")
    transaction_hash: str = Field(pattern=r"^0x[a-fA-F0-9]{64}$")
    block_number: int = Field(ge=0)
    digest: str = Field(pattern=r"^0x[a-fA-F0-9]{64}$")
    verified: Literal[True]


class RiskEvaluationResponse(StrictModel):
    request_id: str
    verdict: Literal["ALLOW_FOR_FURTHER_CHECKS", "BLOCK", "REVIEW", "UNAVAILABLE"]
    execution_authorized: Literal[False] = False
    reason_codes: list[str]
    evidence_ids: list[str]
    evaluated_at: AwareDatetime
    source_mode: Literal["MOCK", "MARKET_ONLY"]
    policy_version: Literal["risk-service-1.1.0"] = "risk-service-1.1.0"
    chain_receipt: VerifiedChainReceipt | None = None


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
    version: Literal["1.1.0"] = "1.1.0"
    notional_source_mode: Literal["MOCK", "MARKET_ONLY"]
    legacy_quantity_supported: Literal[True] = True
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
