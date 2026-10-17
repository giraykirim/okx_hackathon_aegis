/**
 * AEGIS Shared API v2 + Additive Service v1 TypeScript Contract
 *
 * Strictly mirrors:
 * - contracts/openapi.yaml (Frozen v2 SHA-256: a437caaa81ae590fc258aa0aeeb6498b1c38ec745483a701a4b2f0c66314d5ae)
 * - contracts/service-openapi.yaml (Additive amendment contract)
 */

export type SourceMode = "MOCK" | "MARKET_ONLY" | "OKX_DEMO";
export type ExecutionStatus = "NOT_SENT" | "PENDING" | "VERIFIED" | "FAILED" | "UNKNOWN";
export type LayaLabel = "CONTINUE" | "REVIEW" | "HALT";
export type ProposedAction = "NO_TRADE" | "BUY" | "SELL";
export type CapabilityStatus = "PASS" | "FAIL" | "NOT_TESTED";
export type EventSeverity = "INFO" | "WARNING" | "ERROR";

export type ScenarioType =
  | "normal"
  | "stale_feed"
  | "laya_halt"
  | "excess_exposure"
  | "invalid_quantity"
  | "missing_approval"
  | "unknown_order"
  | "duplicate_intent";

export interface Health {
  status: "ok";
  running: boolean;
  source_mode: SourceMode;
  live_execution_enabled: false;
}

export interface Capability {
  status: CapabilityStatus;
  evidence: string[];
  checked_at: string | null;
}

export interface Classification {
  label: LayaLabel;
  confidence: number;
  abstained: boolean;
  model_version: string;
  latency_ms: number;
}

export interface Observation {
  symbol: "BTC-USDT";
  observed_at: string;
  price: string;
  ask: string;
  bid: string;
  min_size: string;
  lot_size: string;
  tick_size?: string;
  instrument_live: boolean;
  account_known?: boolean;
  exposure_quote?: string;
  quote_available?: string;
  base_available?: string;
  account_observed_at?: string | null;
  external_open_orders?: boolean;
}

export interface Decision {
  id?: string;
  timestamp?: string;
  run_id: string;
  symbol: "BTC-USDT";
  proposed_action: ProposedAction;
  laya_label: LayaLabel;
  laya_confidence: number;
  llm_summary: string;
  evidence_ids: string[];
  risk_approved: boolean;
  risk_reasons: string[];
  execution_status: ExecutionStatus;
  venue_order_id?: string | null;
  source_mode: SourceMode;
  intent_id: string;
  quantity: string;
  venue_state?: string | null;
  limit_price?: string | null;
}

export interface EventItem {
  id?: string;
  timestamp?: string;
  run_id: string;
  type: string;
  severity: EventSeverity;
  actor: string;
  message: string;
  details?: Record<string, unknown>;
  source_mode: SourceMode;
}

export interface Identity {
  chain_id: 43113;
  registry_address: string | null;
  agent_id: string | null;
  agent_uri: string | null;
  owner: string | null;
  registration_tx_hash: string | null;
  tx_hash: string | null;
  verified: boolean;
  verification_checked_at: string | null;
  verification_status: string;
}

export interface Metrics {
  decisions: number;
  vetoed: number;
  verified_exchange_orders: number;
  mock_executions: number;
  unresolved_orders: number;
  pnl: null;
}

export interface Snapshot {
  running: boolean;
  run_id: string;
  source_mode: SourceMode;
  last_cycle_at: string | null;
  observation: Observation | null;
  classification: Classification | null;
  latest_decision: Decision | null;
  capabilities: Record<string, Capability>;
  identity: Identity;
  execution_enabled: boolean;
}

export interface ControlState {
  running: boolean;
  run_id: string;
  source_mode: SourceMode;
}

// --- Additive Service Contract (contracts/service-openapi.yaml) ---

export interface RiskRequestInput {
  symbol: "BTC-USDT";
  action: "BUY" | "SELL";
  quantity: string | number;
  client_request_id?: string | null;
}

export interface RiskRequestOutput {
  symbol: "BTC-USDT";
  action: "BUY" | "SELL";
  quantity: string;
  client_request_id?: string | null;
}

export interface ATKReceipt {
  id: string;
  toolkit: string;
  operation: "ticker" | "instruments";
  command: string[];
  site: string;
  requested_at: string;
  completed_at: string;
  market_timestamp: string | null;
  source_mode: "MARKET_ONLY" | "OKX_DEMO";
  run_id: string;
  status: "PASS" | "FAIL";
  result_sha256: string | null;
  stdout_sha256: string | null;
  elapsed_ms: number;
  error_type?: string | null;
}

export interface MarketProvenance {
  status: "PASS" | "FAIL" | "UNAVAILABLE";
  source: "OFFICIAL_OKX_ATK";
  site: string;
  market_timestamp: string | null;
  receipts: ATKReceipt[];
}

export interface MarketChecks {
  status: "PASS" | "FAIL" | "UNAVAILABLE";
  reasons: string[];
  policy_limit_price: string | null;
}

export interface RiskAssessment {
  assessment_id: string;
  timestamp: string;
  run_id: string;
  request: RiskRequestOutput;
  source_mode: "MARKET_ONLY";
  assessment: "REVIEW" | "HALT";
  reasons: string[];
  execution_authority: false;
  order_permission: false;
  account_provenance: "UNAVAILABLE";
  market_provenance: MarketProvenance;
  market_checks: MarketChecks;
  classification: Classification;
  laya_status: "AVAILABLE" | "UNAVAILABLE";
  evren_status: "AVAILABLE" | "FALLBACK";
  analysis_summary: string;
  limitations: string[];
  evidence_ids: string[];
  assessment_sha256: string;
}

export interface ServiceAuth {
  scheme: "api_key";
  header: "X-AEGIS-Key";
  required: true;
  configured: boolean;
  requests_per_minute: number;
  concurrent_assessments: 1;
  max_request_bytes: 2048;
  scope: string;
}

export interface ProposedPricing {
  status: "PROPOSED_NOT_BILLED";
  currency: "USD";
  per_assessment: string;
  b2b_monthly: string;
  included_assessments: number;
  payment_integration: "NOT_IMPLEMENTED";
}

export interface MarketplaceStatus {
  listing_status: "NOT_LISTED";
  integration_feasibility: "POSSIBLE";
  verified_listing_url: null;
  requirements_url: string;
}

export interface ServiceInfo {
  name: string;
  version: string;
  purpose: string;
  target_customer: string;
  execution_authority: false;
  public_url: null;
  deployment_status: "PUBLIC_NOT_VERIFIED" | "LOCAL_ONLY";
  evaluate_path: "/api/v1/risk/evaluate";
  auth: ServiceAuth;
  pricing: ProposedPricing;
  okx_ai: MarketplaceStatus;
  limitations: string[];
}

// --- Service 1.1.0 String-Notional Contract (contracts/PERSON3_HANDOFF.md) ---

export type NotionalVerdict =
  | "UNAVAILABLE"
  | "BLOCK"
  | "ALLOW_FOR_FURTHER_CHECKS";

export interface NotionalRiskRequest {
  request_id: string;
  symbol: "BTC-USDT";
  proposed_action: "BUY" | "SELL" | "NO_TRADE";
  proposed_notional: string;
  requester_context?: Record<string, unknown> | null;
}

export interface NotionalRiskResponse {
  request_id: string;
  verdict: NotionalVerdict;
  execution_authorized: false;
  reason_codes: string[];
  evidence_ids: string[];
  evaluated_at: string;
  source_mode: SourceMode;
  policy_version: string;
  chain_receipt: Record<string, unknown> | null;
}

export type RuntimeConnectionState =
  | "LIVE_CONNECTED"
  | "POLLING_FALLBACK"
  | "HISTORICAL_EVIDENCE"
  | "MOCK_SIMULATION"
  | "BACKEND_OFFLINE"
  | "UNKNOWN";

export type Erc8004RegistrationState =
  | "NOT_CONFIGURED"
  | "REGISTRY_AVAILABLE"
  | "REGISTRATION_PENDING"
  | "REGISTERED_VERIFIED"
  | "VERIFICATION_FAILED"
  | "UNAVAILABLE";

export type AuditProofState =
  | "ONCHAIN_AUDIT_PROOF"
  | "LOCAL_AUDIT_DIGEST"
  | "UNAVAILABLE";

export type PipelineStageStatus =
  | "COMPLETED"
  | "RUNNING"
  | "SKIPPED"
  | "BLOCKED"
  | "FALLBACK"
  | "UNAVAILABLE"
  | "NOT_TESTED"
  | "IDLE";


