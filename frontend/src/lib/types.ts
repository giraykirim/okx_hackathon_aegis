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

export interface PnlMark {
  symbol: string;
  price: string;
  bid: string;
  ask: string;
  observed_at: string;
  source: string;
  age_seconds: number;
  stale: boolean;
  max_age_seconds: number;
}

/** Backend `/api/metrics/pnl` (schema `aegis-demo-pnl-2`); all money values are decimal strings. */
export interface DemoPnl {
  schema_version: "aegis-demo-pnl-2";
  /** Accounting figures are null when an accounting issue makes them unknowable (see `issues`). */
  realized: string | null;
  unrealized: string | null;
  net: string | null;
  /** Quote-equivalent fee cost (positive = cost, negative = net rebate); already inside net. */
  fees: string | null;
  fee_breakdown: Record<string, string>;
  inventory_qty: string | null;
  cost_basis: string | null;
  average_cost: string | null;
  fill_count: number;
  unmatched_sell_qty: string;
  complete: boolean;
  issues: string[];
  warnings: string[];
  ledger: Record<string, unknown>[];
  mark_price: string | null;
  mark: PnlMark | null;
  valuation_status:
    | "CURRENT_MARK"
    | "STALE_MARK"
    | "NO_MARK"
    | "CLOSED_NO_MARK_NEEDED"
    | "ACCOUNTING_INCOMPLETE";
  excluded_unowned_fills: number;
  method: string;
  as_of: string;
}

export interface CostAssessment {
  status: "APPROVED" | "NO_TRADE" | "REVIEW" | "NOT_APPLICABLE";
  approved: boolean;
  reasons: string[];
  explanation: string;
  inputs: Record<string, unknown>;
  breakdown: Record<string, unknown> | null;
}

/** Backend `/api/metrics/cost-gate` (schema `aegis-cost-gate-1`). */
export interface CostGateSummary {
  schema_version: "aegis-cost-gate-1";
  evaluated_trade_proposals: number;
  cost_approved: number;
  blocked_when_enforced: number;
  would_block_unenforced: number;
  reason_counts: Record<string, number>;
  latest: {
    decision_id: string;
    source_mode: string;
    timestamp: string;
    enforced: boolean;
    assessment: CostAssessment;
  } | null;
}

/** Advisory exit proposal from backend `aegis/exit_plan.py`; never executable. */
export interface ExitProposal {
  status: "PROPOSE_REDUCE" | "PROPOSE_CLOSE" | "NO_EXIT" | "REVIEW";
  reasons: string[];
  rule_set: "position_reduction_v1";
  entry_edge_gate_applies: false;
  executable: false;
  order_adapter: null;
  requested_fraction: string;
  owned_net_btc: string | null;
  sellable_btc: string | null;
  proposed_sell_btc: string | null;
  remaining_btc: string | null;
  lot_size: string | null;
  min_size: string | null;
  reference_bid: string | null;
  market_observed_at: string | null;
  market_age_seconds: number | null;
  explanation: string;
}

/** One persisted cycle assessment (schema `aegis-exit-shadow-1`). */
export interface ExitShadowAssessment {
  schema_version: "aegis-exit-shadow-1";
  assessment_id: string;
  run_id: string;
  cycle_id: string;
  source_mode: SourceMode;
  computed_at: string;
  mode: "SHADOW";
  orders_sent: false;
  /** fraction=1 is full-close capacity after lot/minimum limits, not a signal to sell now. */
  fraction_semantics: "full_close_capacity_not_a_sell_signal";
  market_source: string | null;
  /** Market bound the read view re-applies to `proposal.market_observed_at`. */
  market_max_age_seconds: number;
  inventory_basis: {
    fingerprint: string;
    owned_fill_count: number;
    excluded_unowned_fills: number;
    unresolved_demo_orders: number;
  };
  proposal: ExitProposal;
}

/** Backend `/api/metrics/exit-shadow` (schema `aegis-exit-shadow-read-1`); a read never recomputes. */
export interface ExitShadowRead {
  schema_version: "aegis-exit-shadow-read-1";
  mode: "SHADOW";
  orders_sent: false;
  executable: false;
  read_at: string;
  max_age_seconds: number;
  state: "NO_ASSESSMENT" | "CURRENT" | "STALE" | "SUPERSEDED";
  current: boolean;
  age_seconds: number | null;
  /** True when the outcome (capacity or lot/minimum result) was derived from market data. */
  market_dependent: boolean;
  /** Age of that market observation at read time, judged apart from the record age. */
  market_age_seconds: number | null;
  market_max_age_seconds: number | null;
  not_current_reasons: string[];
  assessment: ExitShadowAssessment | null;
}

export interface Metrics {
  decisions: number;
  vetoed: number;
  verified_exchange_orders: number;
  mock_executions: number;
  unresolved_orders: number;
  /** Account-level profit is deliberately not asserted. */
  pnl: null;
  /**
   * Client-side merge of the additive `/api/metrics/pnl` endpoint.
   * Mark-to-market PnL of verified demo fills only; absent when no fills exist.
   */
  demo_pnl?: DemoPnl | null;
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

// --- Optional TradeCourt Council Contract (Frontend Integration-Ready) ---

export type CouncilLifecycleState =
  | "LOADING"
  | "UNAVAILABLE"
  | "SKIPPED"
  | "COMPLETED"
  | "DEGRADED";

export type CouncilSeatId =
  | "REGIME_MAGISTRATE"
  | "OPPORTUNITY_ADVOCATE"
  | "RISK_PROSECUTOR"
  | "PRESIDING_ARBITER";

export type CouncilMemberStance =
  | "APPROVE"
  | "CAUTION"
  | "VETO"
  | "ABSTAIN";

export type CouncilSeatStatus =
  | "COMPLETED"
  | "DEGRADED"
  | "SKIPPED"
  | "UNAVAILABLE"
  | "LOADING"
  | "MOCK_SCRIPTED";

export interface CouncilMemberVerdict {
  seatId: CouncilSeatId;
  roleTitle: string;
  subtitle: string;
  modelName: string | null;
  actor: "laya" | "evren" | "policy" | "mock";
  status: CouncilSeatStatus;
  stance: CouncilMemberStance;
  confidence: number | null;
  latencyMs: number | null;
  rationale: string;
  flaggedRules: string[];
  evidenceId: string | null;
  isAdvisoryOnly: boolean;
  isMockData: boolean;
}

export interface TradeCourtSession {
  sessionId: string;
  runId: string;
  cycleId: string | null;
  timestamp: string | null;
  state: CouncilLifecycleState;
  isMockFixture: boolean;
  sourceMode: SourceMode;
  symbol: "BTC-USDT";
  proposedAction: ProposedAction;
  proposedQuantity: string;
  consensusStance: "NO_TRADE" | "REVIEW" | "PROCEED_TO_GATE" | "HALT";
  finalGateApproved: boolean;
  headline: string;
  summary: string;
  authorityNotice: string;
  seats: CouncilMemberVerdict[];
  activeRiskReasons: string[];
  totalDeliberationMs: number | null;
}
