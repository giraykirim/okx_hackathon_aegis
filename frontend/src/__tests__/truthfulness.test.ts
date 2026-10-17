import { describe, expect, it } from "vitest";
import {
  RECORDED_EVENTS_MARKET_ONLY,
  RECORDED_METRICS_MARKET_ONLY,
  RECORDED_MOCK_SCENARIOS,
  RECORDED_NOTIONAL_ASSESSMENTS,
  RECORDED_SERVICE_ASSESSMENTS,
  RECORDED_SERVICE_INFO,
  RECORDED_SNAPSHOT_MARKET_ONLY,
} from "../lib/fixtures";
import { isAdminAuthorized } from "../lib/server-backend";
import type { EventItem, Snapshot } from "../lib/types";
import {
  buildPipelineSteps,
  deriveAccurateMetrics,
  deriveAuditProofState,
  deriveDecisionSemantics,
  deriveErc8004RegistrationState,
  deriveRuntimeStatusModel,
  describeEvrenModelState,
  describeLayaModelState,
  explainRiskReason,
  extractAtkReceipts,
  formatAccountBalance,
  getSourceModeExplanation,
} from "../lib/view-helpers";

describe("AEGIS Final Frontend Audit, Truthfulness & Null-Safety Suite", () => {
  it("1. distinguishes Live Connected vs Historical ATK Evidence vs Polling Fallback vs Mock Simulation (P0-1)", () => {
    const liveStatus = deriveRuntimeStatusModel({
      backendReachable: true,
      isOfflineFixture: false,
      activeScenario: "live_backend",
      sourceMode: "MARKET_ONLY",
      sseStatus: "LIVE",
      lastTimestampIso: "2026-10-17T09:31:45.524741Z",
      nowMs: Date.parse("2026-10-17T09:32:00.000Z"),
    });
    expect(liveStatus.state).toBe("LIVE_CONNECTED");
    expect(liveStatus.badgeLabel).toBe("Live Market Monitoring");
    expect(liveStatus.isLiveConnected).toBe(true);
    expect(liveStatus.relativeAgeText).toContain("14s ago");

    const offlineStatus = deriveRuntimeStatusModel({
      backendReachable: false,
      isOfflineFixture: true,
      activeScenario: "recorded_market_only",
      sourceMode: "MARKET_ONLY",
      sseStatus: "FALLBACK",
      lastTimestampIso: "2026-10-17T09:31:45.524741Z",
      nowMs: Date.parse("2026-10-17T10:01:45.524741Z"),
    });
    expect(offlineStatus.state).toBe("HISTORICAL_EVIDENCE");
    expect(offlineStatus.badgeLabel).toBe("Historical ATK Evidence");
    expect(offlineStatus.subtitle).toContain("Backend offline");
    expect(offlineStatus.isLiveConnected).toBe(false);
    expect(offlineStatus.relativeAgeText).toContain("30m ago");

    const pollingStatus = deriveRuntimeStatusModel({
      backendReachable: true,
      isOfflineFixture: false,
      activeScenario: "live_backend",
      sourceMode: "MARKET_ONLY",
      sseStatus: "FALLBACK",
      lastTimestampIso: "2026-10-17T09:31:45.524741Z",
    });
    expect(pollingStatus.state).toBe("POLLING_FALLBACK");
    expect(pollingStatus.badgeLabel).toBe("Polling Fallback");

    const mockStatus = deriveRuntimeStatusModel({
      backendReachable: true,
      isOfflineFixture: false,
      activeScenario: "mock_stale_feed",
      sourceMode: "MOCK",
      lastTimestampIso: "2026-10-17T09:31:45.567580Z",
    });
    expect(mockStatus.state).toBe("MOCK_SIMULATION");
    expect(mockStatus.badgeLabel).toBe("Mock Simulation");
  });

  it("2. enforces ERC-8004 Registry Ready vs Registered & Verified on Avalanche Fuji (P0-2)", () => {
    // Registry contract detected on Fuji 43113, but agent not minted yet
    const registryReady = deriveErc8004RegistrationState({
      chainId: 43113,
      identityRegistryAddress: "0x8004A818BFB912233c491871b3d84c89A494BD9e",
      identityRegistryHasCode: true,
      agentId: null,
      owner: null,
      agentUri: null,
      verified: false,
      verificationStatus: "NOT_TESTED",
    });
    expect(registryReady.state).toBe("REGISTRY_AVAILABLE");
    expect(registryReady.badgeLabel).toBe("ERC-8004 Registry Ready");
    expect(registryReady.headline).toBe("ERC-8004 Registry Ready");
    expect(registryReady.headline).not.toContain(
      "Registered as an ERC-8004 agent"
    );
    expect(registryReady.subtitle).toBe(
      "Registry contract detected on Avalanche Fuji. Agent registration is pending."
    );
    expect(registryReady.isVerified).toBe(false);

    // Full verified ERC-8004 registration
    const registeredVerified = deriveErc8004RegistrationState({
      chainId: 43113,
      identityRegistryAddress: "0x8004A818BFB912233c491871b3d84c89A494BD9e",
      identityRegistryHasCode: true,
      agentId: 264,
      owner: "0x725967879187c34999A86A5015fFf934886A9C6e",
      agentUri: "https://aegis.example/agent-registration.json",
      verified: true,
      verificationStatus: "PASS",
    });
    expect(registeredVerified.state).toBe("REGISTERED_VERIFIED");
    expect(registeredVerified.badgeLabel).toBe("AEGIS Registered & Verified");
    expect(registeredVerified.isVerified).toBe(true);
  });

  it("3. distinguishes Local Audit Digest from On-chain Audit Proof (P0-3)", () => {
    const localDigest = deriveAuditProofState({
      canonicalDecisionHash:
        "0x166c93073c84eddf94e432f3b0a52a66f60a6c308097beed0527097cfb3c08b2",
      contractAddress: null,
      txHash: null,
      verified: false,
    });
    expect(localDigest.state).toBe("LOCAL_AUDIT_DIGEST");
    expect(localDigest.title).toBe("Local Audit Digest");
    expect(localDigest.subtitle).toBe(
      "Cryptographic digest of a recorded decision. Not anchored on-chain."
    );
    expect(localDigest.anchorStatusText).toBe("Not yet anchored on-chain");
    expect(localDigest.isAnchoredOnChain).toBe(false);
    expect(localDigest.canLinkExplorer).toBe(false);

    const onChainProof = deriveAuditProofState({
      canonicalDecisionHash:
        "0x166c93073c84eddf94e432f3b0a52a66f60a6c308097beed0527097cfb3c08b2",
      contractAddress: "0x1111111111111111111111111111111111111111",
      txHash:
        "0x2222222222222222222222222222222222222222222222222222222222222222",
      verified: true,
    });
    expect(onChainProof.state).toBe("ONCHAIN_AUDIT_PROOF");
    expect(onChainProof.title).toBe("On-chain Audit Proof");
    expect(onChainProof.isAnchoredOnChain).toBe(true);
    expect(onChainProof.canLinkExplorer).toBe(true);
  });

  it("4. separates voluntary NO_TRADE decisions from genuine POLICY_VETOED trade blocks and keeps metrics consistent (P0-4 & P1-5)", () => {
    const marketOnlyDecision = RECORDED_SNAPSHOT_MARKET_ONLY.latest_decision!;
    const noTradeSem = deriveDecisionSemantics(marketOnlyDecision);
    expect(noTradeSem.verdictType).toBe("NO_TRADE");
    expect(noTradeSem.isVoluntaryNoTrade).toBe(true);
    expect(noTradeSem.isTradeBlockedByPolicy).toBe(false);

    const staleFeedDecision = RECORDED_MOCK_SCENARIOS.stale_feed.decision;
    const vetoSem = deriveDecisionSemantics(staleFeedDecision);
    expect(vetoSem.verdictType).toBe("POLICY_VETOED");
    expect(vetoSem.isTradeBlockedByPolicy).toBe(true);
    expect(vetoSem.isVoluntaryNoTrade).toBe(false);

    // Metrics consistency for MARKET_ONLY (1 voluntary NO_TRADE, 0 policy vetoes)
    const marketMetrics = deriveAccurateMetrics(
      RECORDED_METRICS_MARKET_ONLY,
      [marketOnlyDecision],
      marketOnlyDecision
    );
    expect(marketMetrics.totalDecisions).toBe(1);
    expect(marketMetrics.noTradeDecisions).toBe(1);
    expect(marketMetrics.policyVetoes).toBe(0);
    expect(marketMetrics.hasSufficientTrendHistory).toBe(false);

    // Metrics consistency for MOCK Stale Feed (0 voluntary NO_TRADE, 1 policy veto)
    const mockMetrics = deriveAccurateMetrics(
      {
        decisions: 1,
        vetoed: 1,
        verified_exchange_orders: 0,
        mock_executions: 0,
        unresolved_orders: 0,
        pnl: null,
      },
      [staleFeedDecision],
      staleFeedDecision
    );
    expect(mockMetrics.totalDecisions).toBe(1);
    expect(mockMetrics.noTradeDecisions).toBe(0);
    expect(mockMetrics.policyVetoes).toBe(1);
  });

  it("5. presents LAYA and EVREN unavailability honestly without 0% confidence or 0 ms latency (P1-1 & P1-2)", () => {
    const layaState = describeLayaModelState(
      RECORDED_SNAPSHOT_MARKET_ONLY.classification,
      RECORDED_SNAPSHOT_MARKET_ONLY.capabilities
    );
    expect(layaState.isAvailable).toBe(false);
    expect(layaState.statusTitle).toBe("LAYA Unavailable");
    expect(layaState.subtitle).toBe(
      "Operational classification unavailable. Safe fallback policy active."
    );
    expect(layaState.actionLabel).toBe("Fallback Action: REVIEW");
    expect(layaState.confidenceText).toBe("Confidence: N/A");
    expect(layaState.latencyText).toBe("Model latency: Not measured");
    expect(layaState.measuredDurationMs).toBeNull();
    expect(layaState.pipelineStatus).toBe("UNAVAILABLE");

    const evrenState = describeEvrenModelState(
      RECORDED_SNAPSHOT_MARKET_ONLY.latest_decision,
      RECORDED_SNAPSHOT_MARKET_ONLY.capabilities
    );
    expect(evrenState.isAvailable).toBe(false);
    expect(evrenState.statusTitle).toBe("Reasoning Provider Unavailable");
    expect(evrenState.subtitle).toBe(
      "Deterministic NO_TRADE fallback applied."
    );
    expect(evrenState.badgeText).toBe("Fallback Applied");
    expect(evrenState.latencyText).toBe("Model latency: Not measured");
    expect(evrenState.measuredDurationMs).toBeNull();
    expect(evrenState.pipelineStatus).toBe("FALLBACK");
  });

  it("6. never claims real $0 balance when account_known is false (MARKET_ONLY)", () => {
    const accountView = formatAccountBalance(
      RECORDED_SNAPSHOT_MARKET_ONLY.observation
    );
    expect(RECORDED_SNAPSHOT_MARKET_ONLY.observation?.account_known).toBe(
      false
    );
    expect(accountView.statusLabel).toBe("UNAVAILABLE");
    expect(accountView.quoteDisplay).toContain("UNAVAILABLE");
    expect(accountView.baseDisplay).toContain("UNAVAILABLE");
  });

  it("7. handles null observation, classification, and latest_decision gracefully without crashing", () => {
    const emptySnapshot: Snapshot = {
      running: false,
      run_id: "empty-run",
      source_mode: "MARKET_ONLY",
      last_cycle_at: null,
      observation: null,
      classification: null,
      latest_decision: null,
      capabilities: {},
      identity: {
        chain_id: 43113,
        registry_address: null,
        agent_id: null,
        agent_uri: null,
        owner: null,
        registration_tx_hash: null,
        tx_hash: null,
        verified: false,
        verification_checked_at: null,
        verification_status: "NOT_TESTED",
      },
      execution_enabled: false,
    };

    const accountView = formatAccountBalance(emptySnapshot.observation);
    expect(accountView.statusLabel).toBe("UNAVAILABLE");

    const steps = buildPipelineSteps(emptySnapshot, []);
    expect(steps).toHaveLength(7);
    expect(steps.every((s) => s.status === "IDLE")).toBe(true);
  });

  it("8. marks VERIFY stage as SKIPPED (never COMPLETED) when execution_status is NOT_SENT (Section 14)", () => {
    const receipts = extractAtkReceipts(
      RECORDED_EVENTS_MARKET_ONLY,
      RECORDED_SNAPSHOT_MARKET_ONLY.run_id
    );
    expect(receipts.length).toBeGreaterThanOrEqual(2);
    expect(receipts[0].toolkit).toBe("@okx_ai/okx-trade-cli@1.4.8");
    expect(receipts[0].site).toBe("tr");

    const steps = buildPipelineSteps(
      RECORDED_SNAPSHOT_MARKET_ONLY,
      RECORDED_EVENTS_MARKET_ONLY
    );
    expect(steps).toHaveLength(7);

    const observeStep = steps.find((s) => s.key === "OBSERVE")!;
    expect(observeStep.status).toBe("COMPLETED");
    expect(observeStep.measuredDurationMs).toBeGreaterThan(1000);

    const classifyStep = steps.find((s) => s.key === "CLASSIFY")!;
    expect(classifyStep.status).toBe("UNAVAILABLE");
    expect(classifyStep.verdictBadge).toContain("Confidence: N/A");

    const reasonStep = steps.find((s) => s.key === "REASON")!;
    expect(reasonStep.status).toBe("FALLBACK");

    const gateStep = steps.find((s) => s.key === "RISK_GATE")!;
    expect(gateStep.status).toBe("BLOCKED");

    const actionStep = steps.find((s) => s.key === "ACTION")!;
    expect(actionStep.status).toBe("SKIPPED");

    const verifyStep = steps.find((s) => s.key === "VERIFY")!;
    expect(verifyStep.status).toBe("SKIPPED");
    expect(verifyStep.verdictBadge).toContain(
      "NOT_SENT — No exchange verification required"
    );
  });

  it("9. exposes all 8 official ATK/MCP capabilities with honest PASS vs NOT_TESTED statuses", () => {
    const caps = RECORDED_SNAPSHOT_MARKET_ONLY.capabilities;
    expect(caps.ATK_PACKAGE_INSTALLED?.status).toBe("PASS");
    expect(caps.ATK_MARKET_READ?.status).toBe("PASS");
    expect(caps.ATK_MCP_LIST_TOOLS?.status).toBe("PASS");
    expect(caps.ATK_MCP_CALL_TOOL?.status).toBe("PASS");
    expect(caps.ATK_TR_ROUTING?.status).toBe("PASS");
    expect(caps.ATK_DEMO_ACCOUNT_READ?.status).toBe("NOT_TESTED");
    expect(caps.ATK_DEMO_ORDER_SUBMISSION?.status).toBe("NOT_TESTED");
    expect(caps.ATK_ORDER_RECONCILIATION?.status).toBe("NOT_TESTED");
  });

  it("10. resolves Event.details.phase (OBSERVE/CLASSIFY/REASON/RISK_CHECK/NO_TRADE/VERIFY/AUDIT)", () => {
    const phaseEvents: EventItem[] = [
      {
        id: "ev-phase-test",
        timestamp: "2026-10-17T10:50:11Z",
        run_id: RECORDED_SNAPSHOT_MARKET_ONLY.run_id,
        source_mode: "MARKET_ONLY",
        type: "PHASE_EVENT",
        severity: "INFO",
        actor: "policy",
        message: "Phase event test",
        details: { phase: "RISK_CHECK", duration_ms: 42 },
      },
    ];
    const steps = buildPipelineSteps(RECORDED_SNAPSHOT_MARKET_ONLY, phaseEvents);
    const gateStep = steps.find((s) => s.key === "RISK_GATE")!;
    expect(gateStep.measuredDurationMs).toBe(42);
  });

  it("11. distinguishes MOCK scenarios from real exchange execution (execution_status=NOT_SENT)", () => {
    for (const key of Object.keys(RECORDED_MOCK_SCENARIOS) as Array<
      keyof typeof RECORDED_MOCK_SCENARIOS
    >) {
      const scenario = RECORDED_MOCK_SCENARIOS[key];
      expect(scenario.snapshot.source_mode).toBe("MOCK");
      expect(scenario.decision.source_mode).toBe("MOCK");
      expect(scenario.decision.execution_status).toBe("NOT_SENT");
      expect(scenario.decision.risk_approved).toBe(false);
    }

    const modeBadge = getSourceModeExplanation("MOCK");
    expect(modeBadge.badgeText).toContain("MOCK SCENARIO");
  });

  it("12. enforces order_permission=false, execution_authority=false, and View-Only Judge Mode lock", () => {
    expect(RECORDED_SERVICE_INFO.execution_authority).toBe(false);
    expect(RECORDED_SERVICE_INFO.public_url).toBeNull();
    expect(RECORDED_SERVICE_INFO.okx_ai.listing_status).toBe("NOT_LISTED");
    expect(RECORDED_SERVICE_INFO.pricing.status).toBe("PROPOSED_NOT_BILLED");

    expect(RECORDED_SERVICE_ASSESSMENTS.small_intent.order_permission).toBe(
      false
    );
    expect(RECORDED_SERVICE_ASSESSMENTS.small_intent.execution_authority).toBe(
      false
    );
    expect(RECORDED_SERVICE_ASSESSMENTS.excess_notional.assessment).toBe(
      "HALT"
    );
    expect(RECORDED_SERVICE_ASSESSMENTS.excess_notional.reasons).toContain(
      "excess_order_notional"
    );

    expect(
      RECORDED_NOTIONAL_ASSESSMENTS.market_10_usdt.execution_authorized
    ).toBe(false);
    expect(RECORDED_NOTIONAL_ASSESSMENTS.market_10_usdt.verdict).toBe(
      "UNAVAILABLE"
    );
    expect(RECORDED_NOTIONAL_ASSESSMENTS.market_10_usdt.chain_receipt).toBeNull();

    const reqWithoutHeader = new Request(
      "http://localhost:3000/api/agent/start",
      {
        method: "POST",
      }
    );
    const check = isAdminAuthorized(reqWithoutHeader);
    expect(check.authorized).toBe(false);
    expect([401, 503]).toContain(check.statusCode);

    const stale = explainRiskReason("stale_feed");
    expect(stale.ruleId).toBe("stale_feed");
    expect(stale.title).toContain("Stale");
  });
});
