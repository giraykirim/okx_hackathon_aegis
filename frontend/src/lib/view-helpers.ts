/**
 * Pure presentation and derivation helpers for the AEGIS dashboard.
 *
 * Enforces truthfulness rules:
 * - Never infer VERIFIED from MOCK or model output.
 * - Never render `account_known === false` placeholder zeros as real $0 balances.
 * - Compute actual measured step durations from real event timestamps and ATK receipts.
 * - Never fabricate 0% confidence or 0 ms latency when LAYA/EVREN are unavailable.
 * - Distinguish voluntary NO_TRADE proposals from genuine POLICY_VETOED trade blocks.
 * - Distinguish ERC-8004 Registry Ready (bytecode verified, agentId pending) from Registered & Verified.
 * - Distinguish Local Audit Digest (off-chain SHA-256) from On-chain Audit Proof (Fuji tx verified).
 */

import type {
  ATKReceipt,
  AuditProofState,
  Capability,
  Classification,
  Decision,
  Erc8004RegistrationState,
  EventItem,
  Metrics,
  Observation,
  PipelineStageStatus,
  RuntimeConnectionState,
  Snapshot,
  SourceMode,
} from "./types";

export interface PipelineStepView {
  key:
    | "OBSERVE"
    | "CLASSIFY"
    | "REASON"
    | "RISK_GATE"
    | "ACTION"
    | "VERIFY"
    | "AUDIT";
  stepNumber: number;
  title: string;
  actor: string;
  status: PipelineStageStatus | "VETOED";
  statusBadgeLabel: string;
  verdictBadge: string;
  measuredDurationMs: number | null;
  durationDisplay: string;
  timestamp: string | null;
  summary: string;
  evidenceId: string | null;
  sourceMode: SourceMode;
}

export interface RuntimeStatusView {
  state: RuntimeConnectionState;
  badgeLabel: string;
  subtitle: string;
  tone: "mint" | "teal" | "amber" | "red" | "muted";
  relativeAgeText: string;
  isStale: boolean;
  isLiveConnected: boolean;
}

export interface Erc8004StateView {
  state: Erc8004RegistrationState;
  badgeLabel: string;
  headline: string;
  subtitle: string;
  isVerified: boolean;
  isRegistryDetected: boolean;
  tone: "mint" | "amber" | "red" | "muted";
}

export interface AuditProofStateView {
  state: AuditProofState;
  title: string;
  badgeLabel: string;
  subtitle: string;
  anchorStatusText: string;
  isAnchoredOnChain: boolean;
  canLinkExplorer: boolean;
  tone: "mint" | "amber" | "muted";
}

export interface DecisionSemanticsView {
  verdictType: "NO_TRADE" | "POLICY_VETOED" | "EXECUTION_APPROVED" | "IDLE";
  headline: string;
  badgeLabel: string;
  subheadline: string;
  actionSummary: string;
  tone: "calm" | "danger" | "success" | "muted";
  isTradeBlockedByPolicy: boolean;
  isVoluntaryNoTrade: boolean;
}

export interface AccurateMetricsView {
  totalDecisions: number;
  noTradeDecisions: number;
  policyVetoes: number;
  verifiedExchangeOrders: number;
  mockExecutions: number;
  unresolvedOrders: number;
  hasSufficientTrendHistory: boolean;
  historyCount: number;
}

export interface LayaModelView {
  isAvailable: boolean;
  isScriptedMock: boolean;
  statusTitle: string;
  subtitle: string;
  actionLabel: string;
  confidenceText: string;
  latencyText: string;
  measuredDurationMs: number | null;
  pipelineStatus: PipelineStageStatus;
}

export interface EvrenModelView {
  isAvailable: boolean;
  isScriptedMock: boolean;
  statusTitle: string;
  subtitle: string;
  badgeText: string;
  latencyText: string;
  measuredDurationMs: number | null;
  pipelineStatus: PipelineStageStatus;
}

export function formatRelativeAge(
  isoTimestamp?: string | null,
  nowMs: number = Date.now()
): { text: string; ageSeconds: number | null; isStale: boolean } {
  if (!isoTimestamp) {
    return { text: "Timestamp not recorded", ageSeconds: null, isStale: true };
  }
  const parsed = Date.parse(isoTimestamp);
  if (Number.isNaN(parsed)) {
    return { text: "Timestamp invalid", ageSeconds: null, isStale: true };
  }
  const diffSec = Math.max(0, Math.floor((nowMs - parsed) / 1000));
  const isStale = diffSec > 120;

  if (diffSec < 60) {
    return {
      text: `Last updated ${diffSec}s ago`,
      ageSeconds: diffSec,
      isStale,
    };
  }
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) {
    return {
      text: `Last updated ${diffMin}m ago`,
      ageSeconds: diffSec,
      isStale,
    };
  }
  const diffHr = Math.floor(diffMin / 60);
  const remMin = diffMin % 60;
  if (diffHr < 24) {
    return {
      text:
        remMin > 0
          ? `Last updated ${diffHr}h ${remMin}m ago`
          : `Last updated ${diffHr}h ago`,
      ageSeconds: diffSec,
      isStale: true,
    };
  }
  const diffDays = Math.floor(diffHr / 24);
  return {
    text: `Last updated ${diffDays}d ago`,
    ageSeconds: diffSec,
    isStale: true,
  };
}

export function deriveRuntimeStatusModel(params: {
  backendReachable: boolean;
  isOfflineFixture: boolean;
  activeScenario?: string;
  sourceMode?: SourceMode | null;
  sseStatus?: "LIVE" | "FALLBACK" | "CONNECTING";
  lastTimestampIso?: string | null;
  nowMs?: number;
}): RuntimeStatusView {
  const {
    backendReachable,
    isOfflineFixture,
    activeScenario = "live_backend",
    sourceMode = "MARKET_ONLY",
    sseStatus,
    lastTimestampIso,
    nowMs = Date.now(),
  } = params;

  const rel = formatRelativeAge(lastTimestampIso, nowMs);

  // 1. Synthetic Mock Scenario
  if (sourceMode === "MOCK" || activeScenario.startsWith("mock_")) {
    return {
      state: "MOCK_SIMULATION",
      badgeLabel: "Mock Simulation",
      subtitle:
        "Synthetic risk demonstration scenario. No live exchange or wallet writes.",
      tone: "amber",
      relativeAgeText: rel.text,
      isStale: true,
      isLiveConnected: false,
    };
  }

  // 2. Offline / Historical Evidence
  if (
    !backendReachable ||
    isOfflineFixture ||
    activeScenario === "recorded_market_only"
  ) {
    if (lastTimestampIso) {
      return {
        state: "HISTORICAL_EVIDENCE",
        badgeLabel: "Historical ATK Evidence",
        subtitle:
          "Backend offline. Displaying previously recorded observations.",
        tone: "amber",
        relativeAgeText: rel.text,
        isStale: true,
        isLiveConnected: false,
      };
    }
    return {
      state: "BACKEND_OFFLINE",
      badgeLabel: "Backend Offline",
      subtitle: "Backend unreachable. No live stream active.",
      tone: "red",
      relativeAgeText: "No recorded timestamp",
      isStale: true,
      isLiveConnected: false,
    };
  }

  // 3. Connected to Backend via HTTP Polling Fallback
  if (sseStatus === "FALLBACK") {
    return {
      state: "POLLING_FALLBACK",
      badgeLabel: "Polling Fallback",
      subtitle:
        "Connected to AEGIS backend via HTTP polling (SSE stream inactive).",
      tone: "teal",
      relativeAgeText: rel.text,
      isStale: rel.isStale,
      isLiveConnected: true,
    };
  }

  // 4. Connected Live
  return {
    state: "LIVE_CONNECTED",
    badgeLabel: "Live Market Monitoring",
    subtitle: "Connected to live AEGIS runtime with OKX ATK telemetry.",
    tone: "mint",
    relativeAgeText: rel.text,
    isStale: rel.isStale,
    isLiveConnected: true,
  };
}

export function deriveErc8004RegistrationState(params: {
  chainId?: number | null;
  identityRegistryAddress?: string | null;
  identityRegistryHasCode?: boolean | null;
  agentId?: string | number | null;
  owner?: string | null;
  agentUri?: string | null;
  registrationTxHash?: string | null;
  verified?: boolean | null;
  verificationStatus?: string | null;
}): Erc8004StateView {
  const {
    chainId,
    identityRegistryAddress,
    identityRegistryHasCode,
    agentId,
    owner,
    agentUri,
    registrationTxHash,
    verified,
    verificationStatus,
  } = params;

  const isFuji = chainId === 43113;
  const hasRegistryContract =
    Boolean(identityRegistryAddress) && identityRegistryHasCode !== false;
  const hasValidAgentId =
    agentId !== null &&
    agentId !== undefined &&
    String(agentId).trim().length > 0;
  const hasValidOwner = Boolean(owner && owner.startsWith("0x"));
  const hasValidUri = Boolean(agentUri && agentUri.trim().length > 0);

  if (verificationStatus === "FAIL") {
    return {
      state: "VERIFICATION_FAILED",
      badgeLabel: "Verification Failed",
      headline: "ERC-8004 On-Chain Verification Failed",
      subtitle:
        "RPC read-back did not match expected agent identity parameters on Avalanche Fuji.",
      isVerified: false,
      isRegistryDetected: hasRegistryContract,
      tone: "red",
    };
  }

  // Only show REGISTERED_VERIFIED if ALL criteria in Section 3 are satisfied
  if (
    isFuji &&
    hasRegistryContract &&
    hasValidAgentId &&
    hasValidOwner &&
    hasValidUri &&
    verified === true
  ) {
    return {
      state: "REGISTERED_VERIFIED",
      badgeLabel: "AEGIS Registered & Verified",
      headline: "Registered as an ERC-8004 agent on Avalanche Fuji",
      subtitle:
        "Agent identity token minted and verified via on-chain RPC read-back on Avalanche Fuji (43113).",
      isVerified: true,
      isRegistryDetected: true,
      tone: "mint",
    };
  }

  if (isFuji && hasRegistryContract && registrationTxHash && !verified) {
    return {
      state: "REGISTRATION_PENDING",
      badgeLabel: "Agent Registration Pending",
      headline: "ERC-8004 Agent Registration Pending",
      subtitle:
        "Registration transaction submitted on Avalanche Fuji; awaiting RPC read-back verification.",
      isVerified: false,
      isRegistryDetected: true,
      tone: "amber",
    };
  }

  if (isFuji && (hasRegistryContract || identityRegistryHasCode === true)) {
    return {
      state: "REGISTRY_AVAILABLE",
      badgeLabel: "ERC-8004 Registry Ready",
      headline: "ERC-8004 Registry Ready",
      subtitle:
        "Registry contract detected on Avalanche Fuji. Agent registration is pending.",
      isVerified: false,
      isRegistryDetected: true,
      tone: "amber",
    };
  }

  if (!chainId && !identityRegistryAddress) {
    return {
      state: "UNAVAILABLE",
      badgeLabel: "Status Unavailable",
      headline: "ERC-8004 Status Unavailable",
      subtitle: "On-chain probe data is currently unavailable.",
      isVerified: false,
      isRegistryDetected: false,
      tone: "muted",
    };
  }

  return {
    state: "NOT_CONFIGURED",
    badgeLabel: "Not Yet Registered",
    headline: "ERC-8004 Identity Not Configured",
    subtitle:
      "Avalanche Fuji ERC-8004 agent registration has not been completed in this environment.",
    isVerified: false,
    isRegistryDetected: false,
    tone: "muted",
  };
}

export function deriveAuditProofState(params: {
  canonicalDecisionHash?: string | null;
  contractAddress?: string | null;
  txHash?: string | null;
  verified?: boolean | null;
}): AuditProofStateView {
  const { canonicalDecisionHash, contractAddress, txHash, verified } = params;

  if (verified === true && contractAddress && txHash) {
    return {
      state: "ONCHAIN_AUDIT_PROOF",
      title: "On-chain Audit Proof",
      badgeLabel: "Anchored on Avalanche Fuji",
      subtitle:
        "Canonical decision SHA-256 digest anchored and verified on Avalanche Fuji (43113).",
      anchorStatusText: "Anchored & verified on Avalanche Fuji",
      isAnchoredOnChain: true,
      canLinkExplorer: true,
      tone: "mint",
    };
  }

  if (canonicalDecisionHash) {
    return {
      state: "LOCAL_AUDIT_DIGEST",
      title: "Local Audit Digest",
      badgeLabel: "Not yet anchored on-chain",
      subtitle:
        "Cryptographic digest of a recorded decision. Not anchored on-chain.",
      anchorStatusText: "Not yet anchored on-chain",
      isAnchoredOnChain: false,
      canLinkExplorer: false,
      tone: "amber",
    };
  }

  return {
    state: "UNAVAILABLE",
    title: "Local Audit Digest",
    badgeLabel: "No digest recorded",
    subtitle: "No canonical decision digest recorded yet.",
    anchorStatusText: "Not yet anchored on-chain",
    isAnchoredOnChain: false,
    canLinkExplorer: false,
    tone: "muted",
  };
}

export function deriveDecisionSemantics(
  decision: Decision | null | undefined
): DecisionSemanticsView {
  if (!decision) {
    return {
      verdictType: "IDLE",
      headline: "IDLE — Awaiting Evaluation Cycle",
      badgeLabel: "AWAITING CYCLE",
      subheadline: "No decision cycle has been evaluated in the current view.",
      actionSummary: "No action proposed",
      tone: "muted",
      isTradeBlockedByPolicy: false,
      isVoluntaryNoTrade: false,
    };
  }

  if (decision.risk_approved) {
    return {
      verdictType: "EXECUTION_APPROVED",
      headline: `APPROVED — ${decision.proposed_action} ${decision.quantity} ${decision.symbol}`,
      badgeLabel: "RISK APPROVED",
      subheadline:
        "All deterministic safety gates passed. Order authorized for isolated venue path.",
      actionSummary: `${decision.proposed_action} (${decision.quantity} BTC) → ${decision.execution_status}`,
      tone: "success",
      isTradeBlockedByPolicy: false,
      isVoluntaryNoTrade: false,
    };
  }

  // Voluntary NO_TRADE: no BUY or SELL execution was proposed
  if (decision.proposed_action === "NO_TRADE") {
    return {
      verdictType: "NO_TRADE",
      headline: "NO_TRADE — No Order Proposed (Safe Read-Only Posture)",
      badgeLabel: "NO_TRADE RECORDED",
      subheadline:
        "No trade execution was requested; deterministic safety gates confirmed read-only posture (NOT_SENT).",
      actionSummary: "NO_TRADE (0 BTC) → NOT_SENT",
      tone: "calm",
      isTradeBlockedByPolicy: false,
      isVoluntaryNoTrade: true,
    };
  }

  // Genuine POLICY_VETOED: BUY or SELL was proposed and blocked by deterministic risk policy
  return {
    verdictType: "POLICY_VETOED",
    headline: `POLICY_VETOED — ${decision.proposed_action} Execution Blocked`,
    badgeLabel: "POLICY VETOED",
    subheadline: `Proposed ${decision.proposed_action} (${decision.quantity} BTC) was rejected by deterministic risk rules before venue submission (NOT_SENT).`,
    actionSummary: `${decision.proposed_action} (${decision.quantity} BTC) → BLOCKED (NOT_SENT)`,
    tone: "danger",
    isTradeBlockedByPolicy: true,
    isVoluntaryNoTrade: false,
  };
}

export function deriveAccurateMetrics(
  metrics: Metrics | null | undefined,
  decisions: Decision[],
  latestDecision?: Decision | null
): AccurateMetricsView {
  // Combine decisions list with latestDecision deduplicated by id
  const byId = new Map<string, Decision>();
  for (const d of decisions) {
    if (d && d.id) byId.set(d.id, d);
  }
  if (latestDecision && latestDecision.id && !byId.has(latestDecision.id)) {
    byId.set(latestDecision.id, latestDecision);
  }
  const uniqueDecisions = Array.from(byId.values());

  if (uniqueDecisions.length > 0) {
    const noTradeDecisions = uniqueDecisions.filter(
      (d) => d.proposed_action === "NO_TRADE"
    ).length;
    const policyVetoes = uniqueDecisions.filter(
      (d) => d.proposed_action !== "NO_TRADE" && !d.risk_approved
    ).length;
    const verifiedExchangeOrders = uniqueDecisions.filter(
      (d) => d.execution_status === "VERIFIED" && d.source_mode === "OKX_DEMO"
    ).length;
    const mockExecutions = uniqueDecisions.filter(
      (d) => d.venue_state === "MOCK_FILLED"
    ).length;

    return {
      totalDecisions: uniqueDecisions.length,
      noTradeDecisions,
      policyVetoes,
      verifiedExchangeOrders: Math.max(
        verifiedExchangeOrders,
        metrics?.verified_exchange_orders ?? 0
      ),
      mockExecutions: Math.max(mockExecutions, metrics?.mock_executions ?? 0),
      unresolvedOrders: metrics?.unresolved_orders ?? 0,
      hasSufficientTrendHistory: uniqueDecisions.length >= 3,
      historyCount: uniqueDecisions.length,
    };
  }

  return {
    totalDecisions: metrics?.decisions ?? 0,
    noTradeDecisions: 0,
    policyVetoes: metrics?.vetoed ?? 0,
    verifiedExchangeOrders: metrics?.verified_exchange_orders ?? 0,
    mockExecutions: metrics?.mock_executions ?? 0,
    unresolvedOrders: metrics?.unresolved_orders ?? 0,
    hasSufficientTrendHistory: false,
    historyCount: 0,
  };
}

export function describeLayaModelState(
  classification: Classification | null | undefined,
  capabilities?: Record<string, Capability>,
  classifyEvent?: EventItem
): LayaModelView {
  if (!classification) {
    return {
      isAvailable: false,
      isScriptedMock: false,
      statusTitle: "LAYA Unavailable",
      subtitle:
        "Operational classification unavailable. Safe fallback policy active.",
      actionLabel: "Fallback Action: REVIEW",
      confidenceText: "Confidence: N/A",
      latencyText: "Model latency: Not measured",
      measuredDurationMs: null,
      pipelineStatus: "IDLE",
    };
  }

  const eventAvail = classifyEvent?.details?.availability as string | undefined;
  const isMockScripted =
    classification.model_version === "MOCK-scripted" ||
    eventAvail === "SCRIPTED";

  if (isMockScripted) {
    return {
      isAvailable: false,
      isScriptedMock: true,
      statusTitle: `LAYA Scripted (${classification.label})`,
      subtitle:
        "Scripted operational classification for synthetic risk scenario.",
      actionLabel: `Scripted Action: ${classification.label}`,
      confidenceText: "Confidence: Scripted (Mock)",
      latencyText: "Model latency: Not measured (Mock)",
      measuredDurationMs: null,
      pipelineStatus: classification.label === "HALT" ? "BLOCKED" : "FALLBACK",
    };
  }

  const isFallback =
    classification.model_version === "advisory-fallback" ||
    eventAvail === "UNAVAILABLE" ||
    (classification.abstained &&
      classification.confidence === 0 &&
      classification.latency_ms === 0) ||
    (capabilities?.LAYA && capabilities.LAYA.status !== "PASS");

  if (isFallback) {
    return {
      isAvailable: false,
      isScriptedMock: false,
      statusTitle: "LAYA Unavailable",
      subtitle:
        "Operational classification unavailable. Safe fallback policy active.",
      actionLabel: `Fallback Action: ${classification.label}`,
      confidenceText: "Confidence: N/A",
      latencyText: "Model latency: Not measured",
      measuredDurationMs: null,
      pipelineStatus: "UNAVAILABLE",
    };
  }

  const measuredMs =
    typeof classification.latency_ms === "number" &&
    classification.latency_ms > 0
      ? Number(classification.latency_ms.toFixed(2))
      : null;

  return {
    isAvailable: true,
    isScriptedMock: false,
    statusTitle: `LAYA Active (${classification.model_version})`,
    subtitle:
      "Local fine-tuned operational risk classifier. CONTINUE never grants order permission.",
    actionLabel: classification.label,
    confidenceText: `Confidence: ${(classification.confidence * 100).toFixed(1)}%`,
    latencyText:
      measuredMs !== null
        ? `Model latency: ${measuredMs} ms`
        : "Model latency: Not measured",
    measuredDurationMs: measuredMs,
    pipelineStatus:
      classification.label === "HALT" ? "BLOCKED" : "COMPLETED",
  };
}

export function describeEvrenModelState(
  decision: Decision | null | undefined,
  capabilities?: Record<string, Capability>,
  reasonEvent?: EventItem
): EvrenModelView {
  if (!decision) {
    return {
      isAvailable: false,
      isScriptedMock: false,
      statusTitle: "Reasoning Idle",
      subtitle: "No cycle evaluated.",
      badgeText: "Idle",
      latencyText: "Model latency: Not measured",
      measuredDurationMs: null,
      pipelineStatus: "IDLE",
    };
  }

  const eventAvail = reasonEvent?.details?.availability as string | undefined;
  const isMockScripted =
    decision.source_mode === "MOCK" ||
    decision.llm_summary.toLowerCase().includes("mock scripted") ||
    eventAvail === "SCRIPTED";

  if (isMockScripted) {
    return {
      isAvailable: false,
      isScriptedMock: true,
      statusTitle: "Scripted Proposal (Mock)",
      subtitle:
        "Scripted trade proposal for synthetic safety test; no external LLM was called.",
      badgeText: "Scripted Mock",
      latencyText: "Model latency: Not measured (Mock)",
      measuredDurationMs: null,
      pipelineStatus: "FALLBACK",
    };
  }

  const summaryLower = decision.llm_summary.toLowerCase();
  const isUnavailable =
    eventAvail === "FALLBACK" ||
    eventAvail === "UNAVAILABLE" ||
    summaryLower.includes("unavailable") ||
    summaryLower.includes("fallback") ||
    (capabilities?.EVREN && capabilities.EVREN.status !== "PASS");

  if (isUnavailable) {
    return {
      isAvailable: false,
      isScriptedMock: false,
      statusTitle: "Reasoning Provider Unavailable",
      subtitle: "Deterministic NO_TRADE fallback applied.",
      badgeText: "Fallback Applied",
      latencyText: "Model latency: Not measured",
      measuredDurationMs: null,
      pipelineStatus: "FALLBACK",
    };
  }

  const measuredMs =
    typeof reasonEvent?.details?.duration_ms === "number" &&
    reasonEvent.details.duration_ms > 0
      ? Number(reasonEvent.details.duration_ms.toFixed(2))
      : null;

  return {
    isAvailable: true,
    isScriptedMock: false,
    statusTitle: "EVREN Schema-Validated Proposal",
    subtitle: decision.llm_summary,
    badgeText: "Completed",
    latencyText:
      measuredMs !== null
        ? `Model latency: ${measuredMs} ms`
        : "Model latency: Measured",
    measuredDurationMs: measuredMs,
    pipelineStatus: "COMPLETED",
  };
}

export function formatAccountBalance(observation: Observation | null): {
  statusLabel: "VERIFIED_ACCOUNT" | "UNAVAILABLE";
  quoteDisplay: string;
  baseDisplay: string;
  exposureDisplay: string;
  openOrdersDisplay: string;
  note: string;
} {
  if (!observation || !observation.account_known) {
    return {
      statusLabel: "UNAVAILABLE",
      quoteDisplay: "UNAVAILABLE (not $0)",
      baseDisplay: "UNAVAILABLE (not 0 BTC)",
      exposureDisplay: "UNAVAILABLE",
      openOrdersDisplay: "UNAVAILABLE",
      note: "account_known=false: External or private account state is not connected. Placeholder zeros are never treated as real balances.",
    };
  }

  return {
    statusLabel: "VERIFIED_ACCOUNT",
    quoteDisplay: `${observation.quote_available ?? "0"} USDT`,
    baseDisplay: `${observation.base_available ?? "0"} BTC`,
    exposureDisplay: `${observation.exposure_quote ?? "0"} USDT`,
    openOrdersDisplay: observation.external_open_orders
      ? "YES (HALT TRIGGER)"
      : "NONE",
    note: observation.account_observed_at
      ? `Observed at ${observation.account_observed_at}`
      : "Scripted MOCK account state",
  };
}

export function extractAtkReceipts(
  events: EventItem[],
  runId?: string
): ATKReceipt[] {
  const filtered = events.filter(
    (ev) => ev.type === "ATK_RECEIPT" && (!runId || ev.run_id === runId)
  );
  const source =
    filtered.length > 0
      ? filtered
      : events.filter((ev) => ev.type === "ATK_RECEIPT");
  return source
    .map((ev) => ev.details as unknown as ATKReceipt)
    .filter((d): d is ATKReceipt =>
      Boolean(d && typeof d.operation === "string")
    );
}

function diffMs(
  startIso?: string | null,
  endIso?: string | null
): number | null {
  if (!startIso || !endIso) return null;
  const t1 = Date.parse(startIso);
  const t2 = Date.parse(endIso);
  if (Number.isNaN(t1) || Number.isNaN(t2) || t2 < t1) return null;
  return Number((t2 - t1).toFixed(2));
}

export function buildPipelineSteps(
  snapshot: Snapshot | null,
  events: EventItem[]
): PipelineStepView[] {
  const mode: SourceMode = snapshot?.source_mode ?? "MARKET_ONLY";
  const targetRunId = snapshot?.latest_decision?.run_id || snapshot?.run_id;

  const runEvents = events.filter(
    (e) => !targetRunId || e.run_id === targetRunId
  );
  const activeEvents = runEvents.length > 0 ? runEvents : events;

  const findLatestEvent = (typesOrPhases: string[]) => {
    for (let i = activeEvents.length - 1; i >= 0; i--) {
      const ev = activeEvents[i];
      const phase =
        typeof ev.details?.phase === "string" ? ev.details.phase : undefined;
      if (
        typesOrPhases.includes(ev.type) ||
        (phase && typesOrPhases.includes(phase))
      ) {
        return ev;
      }
    }
    return undefined;
  };

  const startEv = findLatestEvent(["START"]);
  const observeEv = findLatestEvent(["OBSERVE"]);
  const classifyEv = findLatestEvent(["CLASSIFY"]);
  const reasonEv = findLatestEvent(["REASON"]);
  const gateEv = findLatestEvent(["RISK_GATE", "RISK_CHECK"]);
  const actionEv = findLatestEvent(["NO_TRADE", "EXECUTE", "ACT"]);
  const verifyEv = findLatestEvent(["VERIFY"]);
  const auditEv = findLatestEvent(["AUDIT"]);

  const receipts = extractAtkReceipts(activeEvents, targetRunId);
  const totalAtkMs =
    receipts.length > 0
      ? Number(
          receipts
            .reduce(
              (acc, r) =>
                acc + (typeof r.elapsed_ms === "number" ? r.elapsed_ms : 0),
              0
            )
            .toFixed(2)
        )
      : diffMs(startEv?.timestamp, observeEv?.timestamp);

  const obs = snapshot?.observation;
  const cls = snapshot?.classification;
  const dec = snapshot?.latest_decision;

  const eventDuration = (
    ev: EventItem | undefined,
    fallbackStart?: string | null
  ): number | null => {
    if (typeof ev?.details?.duration_ms === "number") {
      return Number(ev.details.duration_ms.toFixed(2));
    }
    return diffMs(fallbackStart, ev?.timestamp);
  };

  const layaState = describeLayaModelState(
    cls,
    snapshot?.capabilities,
    classifyEv
  );
  const evrenState = describeEvrenModelState(
    dec,
    snapshot?.capabilities,
    reasonEv
  );
  const semantics = deriveDecisionSemantics(dec);

  const gateDuration = eventDuration(gateEv, reasonEv?.timestamp);
  const actionDuration = eventDuration(actionEv, gateEv?.timestamp);
  const verifyDuration =
    dec?.execution_status === "NOT_SENT"
      ? null
      : eventDuration(verifyEv, actionEv?.timestamp);
  const auditDuration = eventDuration(auditEv, verifyEv?.timestamp);

  // Stage 4: Risk Gate status
  const riskGateStatus: PipelineStepView["status"] = !dec
    ? "IDLE"
    : dec.risk_approved
    ? "COMPLETED"
    : "BLOCKED";

  // Stage 5: Action / No-Trade status
  const actionStatus: PipelineStepView["status"] = !dec
    ? "IDLE"
    : dec.risk_approved
    ? "COMPLETED"
    : semantics.isVoluntaryNoTrade
    ? "SKIPPED"
    : "BLOCKED";

  // Stage 6: Verify status (Section 14: NOT_SENT must be SKIPPED, never COMPLETED)
  const verifyStatus: PipelineStepView["status"] = !dec
    ? "IDLE"
    : dec.execution_status === "VERIFIED"
    ? "COMPLETED"
    : dec.execution_status === "NOT_SENT"
    ? "SKIPPED"
    : "NOT_TESTED";

  return [
    {
      key: "OBSERVE",
      stepNumber: 1,
      title: "1. Observe (OKX ATK)",
      actor: observeEv?.actor || (mode === "MOCK" ? "mock" : "atk"),
      status: obs ? "COMPLETED" : "IDLE",
      statusBadgeLabel: obs ? "COMPLETED" : "IDLE",
      verdictBadge: obs
        ? `${obs.symbol} @ ${obs.price} (${mode})`
        : "AWAITING OBSERVATION",
      measuredDurationMs: totalAtkMs,
      durationDisplay:
        totalAtkMs !== null ? `${totalAtkMs} ms` : "Not measured",
      timestamp: obs?.observed_at || observeEv?.timestamp || null,
      summary: obs
        ? `Bid ${obs.bid} / Ask ${obs.ask} | Min ${obs.min_size} BTC | Account: ${
            obs.account_known ? "KNOWN (MOCK)" : "UNAVAILABLE"
          }`
        : "No observation recorded in current snapshot.",
      evidenceId: observeEv?.id || null,
      sourceMode: mode,
    },
    {
      key: "CLASSIFY",
      stepNumber: 2,
      title: "2. Classify (LAYA)",
      actor: classifyEv?.actor || "laya",
      status: !cls ? "IDLE" : layaState.pipelineStatus,
      statusBadgeLabel: !cls
        ? "IDLE"
        : layaState.pipelineStatus === "UNAVAILABLE"
        ? "FALLBACK (UNAVAILABLE)"
        : layaState.pipelineStatus,
      verdictBadge: !cls
        ? "NOT CLASSIFIED"
        : `${layaState.actionLabel} · ${layaState.confidenceText}`,
      measuredDurationMs: layaState.measuredDurationMs,
      durationDisplay: layaState.latencyText,
      timestamp: classifyEv?.timestamp || null,
      summary: `${layaState.statusTitle}: ${layaState.subtitle}`,
      evidenceId: classifyEv?.id || null,
      sourceMode: mode,
    },
    {
      key: "REASON",
      stepNumber: 3,
      title: "3. Reason (EVREN)",
      actor: reasonEv?.actor || "evren",
      status: !dec ? "IDLE" : evrenState.pipelineStatus,
      statusBadgeLabel: !dec ? "IDLE" : evrenState.badgeText.toUpperCase(),
      verdictBadge: dec
        ? `PROPOSE: ${dec.proposed_action} (${dec.quantity} BTC)`
        : "NO PROPOSAL",
      measuredDurationMs: evrenState.measuredDurationMs,
      durationDisplay: evrenState.latencyText,
      timestamp: reasonEv?.timestamp || null,
      summary: dec
        ? `${evrenState.statusTitle} — ${evrenState.subtitle} [Intent: ${dec.intent_id.slice(0, 12)}…]`
        : "Awaiting bounded LLM proposal.",
      evidenceId: reasonEv?.id || null,
      sourceMode: mode,
    },
    {
      key: "RISK_GATE",
      stepNumber: 4,
      title: "4. Deterministic Risk Gate",
      actor: "policy",
      status: riskGateStatus,
      statusBadgeLabel: !dec
        ? "IDLE"
        : dec.risk_approved
        ? "APPROVED"
        : semantics.isVoluntaryNoTrade
        ? "NO_TRADE ENFORCED"
        : "POLICY VETOED",
      verdictBadge: !dec
        ? "IDLE"
        : dec.risk_approved
        ? "APPROVED (POLICY)"
        : `BLOCKED (${dec.risk_reasons.length} rules)`,
      measuredDurationMs: gateDuration,
      durationDisplay:
        gateDuration !== null ? `${gateDuration} ms` : "< 1 ms (deterministic)",
      timestamp: gateEv?.timestamp || dec?.timestamp || null,
      summary: !dec
        ? "Deterministic Python policy has final execution authority."
        : dec.risk_approved
        ? `All hard checks passed. Policy limit price: ${dec.limit_price ?? "N/A"}`
        : `Active safety rules: ${dec.risk_reasons.join(", ")}`,
      evidenceId: gateEv?.id || null,
      sourceMode: mode,
    },
    {
      key: "ACTION",
      stepNumber: 5,
      title: "5. Action / No-Trade",
      actor: actionEv?.actor || "policy",
      status: actionStatus,
      statusBadgeLabel: !dec
        ? "IDLE"
        : dec.risk_approved
        ? "EXECUTED"
        : semantics.isVoluntaryNoTrade
        ? "NO TRADE"
        : "BLOCKED",
      verdictBadge: !dec
        ? "IDLE"
        : !dec.risk_approved || dec.proposed_action === "NO_TRADE"
        ? "NO_TRADE (NOT_SENT)"
        : mode === "MOCK"
        ? "MOCK_FILLED (NOT_SENT)"
        : `${dec.proposed_action} (${dec.execution_status})`,
      measuredDurationMs: actionDuration,
      durationDisplay:
        actionDuration !== null ? `${actionDuration} ms` : "No venue call",
      timestamp: actionEv?.timestamp || null,
      summary: !dec
        ? "No action executed."
        : semantics.isVoluntaryNoTrade
        ? "No trade was proposed; zero exchange writes attempted (NOT_SENT)."
        : !dec.risk_approved
        ? `Proposed ${dec.proposed_action} blocked by deterministic Risk Gate; zero exchange writes attempted (NOT_SENT).`
        : mode === "MOCK"
        ? "Scripted MOCK fill only; execution_status=NOT_SENT (no exchange order sent)."
        : `Order status: ${dec.execution_status}, venue_order_id: ${dec.venue_order_id ?? "null"}`,
      evidenceId: actionEv?.id || null,
      sourceMode: mode,
    },
    {
      key: "VERIFY",
      stepNumber: 6,
      title: "6. Venue Verify",
      actor: verifyEv?.actor || "policy",
      status: verifyStatus,
      statusBadgeLabel: !dec
        ? "IDLE"
        : dec.execution_status === "VERIFIED"
        ? "VERIFIED"
        : dec.execution_status === "NOT_SENT"
        ? "SKIPPED (NOT_SENT)"
        : dec.execution_status,
      verdictBadge: !dec
        ? "IDLE"
        : dec.execution_status === "NOT_SENT"
        ? "NOT_SENT — No exchange verification required"
        : `${dec.execution_status}${dec.venue_state ? ` · ${dec.venue_state}` : ""}`,
      measuredDurationMs: verifyDuration,
      durationDisplay:
        verifyDuration !== null ? `${verifyDuration} ms` : "Not required",
      timestamp: verifyEv?.timestamp || null,
      summary:
        dec?.execution_status === "VERIFIED"
          ? "Independent venue read-back confirmed cash IOC order state."
          : "NOT_SENT — No exchange verification required because no order was submitted to the venue.",
      evidenceId: verifyEv?.id || null,
      sourceMode: mode,
    },
    {
      key: "AUDIT",
      stepNumber: 7,
      title: "7. SQLite Audit & Digest",
      actor: auditEv?.actor || "agent",
      status: !dec ? "IDLE" : "COMPLETED",
      statusBadgeLabel: !dec ? "IDLE" : "RECORDED",
      verdictBadge: dec
        ? `PERSISTED (${dec.evidence_ids.length} evidence IDs)`
        : "AWAITING CYCLE",
      measuredDurationMs: auditDuration,
      durationDisplay:
        auditDuration !== null ? `${auditDuration} ms` : "Persisted",
      timestamp: auditEv?.timestamp || dec?.timestamp || null,
      summary: dec
        ? `Decision ID ${dec.id?.slice(0, 12) ?? "N/A"}… persisted atomically in local SQLite journal.`
        : "No persisted decision in current snapshot.",
      evidenceId: auditEv?.id || dec?.id || null,
      sourceMode: mode,
    },
  ];
}

export function getSourceModeExplanation(mode: SourceMode): {
  badgeText: string;
  badgeClass: string;
  description: string;
} {
  switch (mode) {
    case "MARKET_ONLY":
      return {
        badgeText: "MARKET_ONLY (Real OKX ATK Read)",
        badgeClass: "bg-emerald-500/15 text-emerald-300 border-emerald-500/40",
        description:
          "Real public market & instrument observations via official @okx_ai/okx-trade-cli subprocess (site=tr). Zero exchange order writes.",
      };
    case "MOCK":
      return {
        badgeText: "MOCK SCENARIO (Scripted Simulation)",
        badgeClass: "bg-amber-500/15 text-amber-300 border-amber-500/40",
        description:
          "Synthetic deterministic test mode. Never calls external exchange or claims real execution (execution_status=NOT_SENT).",
      };
    case "OKX_DEMO":
      return {
        badgeText: "OKX_DEMO (Isolated Demo Venue)",
        badgeClass: "bg-sky-500/15 text-sky-300 border-sky-500/40",
        description:
          "Isolated demo account mode. Orders become VERIFIED only after independent exchange read-back reconciliation.",
      };
  }
}

export function explainRiskReason(reason: string): {
  ruleId: string;
  title: string;
  explanation: string;
} {
  const dictionary: Record<string, { title: string; explanation: string }> = {
    execution_disabled: {
      title: "Execution Disabled by Server Policy",
      explanation:
        "Server runtime has execution_enabled=false (e.g. MARKET_ONLY mode). Orders are deterministically blocked.",
    },
    approval_unavailable: {
      title: "Explicit Operator Approval Unavailable",
      explanation:
        "Order execution requires explicit operator risk approval flag; missing approval triggers a fail-closed veto.",
    },
    unknown_account: {
      title: "Account Balances & Exposure Unknown",
      explanation:
        "account_known=false: External account balances and open orders are unavailable. AEGIS never guesses $0 exposure.",
    },
    laya_not_clear: {
      title: "LAYA Operational State Not Clear (REVIEW / HALT / Abstained)",
      explanation:
        "LAYA did not output an un-abstained CONTINUE classification. Policy requires operational clearance before any order.",
    },
    no_trade_proposed: {
      title: "Model Proposed NO_TRADE",
      explanation:
        "EVREN (or its deterministic fallback) proposed NO_TRADE. Policy confirms no order submission.",
    },
    invalid_quantity: {
      title: "Invalid or Zero Order Quantity",
      explanation:
        "Proposed quantity is zero, non-positive, below instrument min_size, or misaligned with lot_size.",
    },
    stale_feed: {
      title: "Stale Market Observation Timestamp",
      explanation:
        "Exchange ticker timestamp age exceeds maximum freshness threshold. Trading on stale market data is forbidden.",
    },
    excess_order_notional: {
      title: "Excess Single-Order Notional Cap Exceeded",
      explanation:
        "Proposed quantity × price exceeds the deterministic single-order notional limit.",
    },
    excess_exposure: {
      title: "Excess Total Account Exposure",
      explanation:
        "Projected post-trade exposure exceeds maximum allowed quote exposure.",
    },
    unresolved_prior_order: {
      title: "Unresolved Prior Order State (PENDING / UNKNOWN)",
      explanation:
        "A prior order has not been reconciled to a terminal state. New submissions are halted to prevent double fills.",
    },
    external_open_orders: {
      title: "External Open Orders Detected on Account",
      explanation:
        "Unreconciled open orders exist on the venue account; deterministic policy halts new order placement.",
    },
    duplicate_intent: {
      title: "Duplicate Intent ID Replay Blocked",
      explanation:
        "intent_id was already claimed in the SQLite idempotency store. Duplicate submission is rejected.",
    },
  };

  const entry = dictionary[reason] || {
    title: `Deterministic Rule: ${reason}`,
    explanation: "Hard policy rule vetoed execution.",
  };

  return {
    ruleId: reason,
    ...entry,
  };
}
