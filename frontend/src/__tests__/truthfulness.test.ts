import { describe, expect, it } from "vitest";
import {
  RECORDED_EVENTS_MARKET_ONLY,
  RECORDED_MOCK_SCENARIOS,
  RECORDED_SERVICE_ASSESSMENTS,
  RECORDED_SERVICE_INFO,
  RECORDED_SNAPSHOT_MARKET_ONLY,
} from "../lib/fixtures";
import { isAdminAuthorized } from "../lib/server-backend";
import type { Snapshot } from "../lib/types";
import {
  buildPipelineSteps,
  explainRiskReason,
  extractAtkReceipts,
  formatAccountBalance,
  getSourceModeExplanation,
} from "../lib/view-helpers";

describe("AEGIS Person 3 Dashboard Truthfulness & Null-Safety Suite", () => {
  it("never claims real $0 balance when account_known is false (MARKET_ONLY)", () => {
    const accountView = formatAccountBalance(
      RECORDED_SNAPSHOT_MARKET_ONLY.observation
    );
    expect(RECORDED_SNAPSHOT_MARKET_ONLY.observation?.account_known).toBe(false);
    expect(accountView.statusLabel).toBe("UNAVAILABLE");
    expect(accountView.quoteDisplay).toContain("UNAVAILABLE");
    expect(accountView.baseDisplay).toContain("UNAVAILABLE");
  });

  it("handles null observation, classification, and latest_decision gracefully without crashing", () => {
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

  it("computes measured step durations and extracts real ATK receipts in MARKET_ONLY mode", () => {
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
    expect(classifyStep.status).toBe("FALLBACK");
    expect(classifyStep.verdictBadge).toContain("REVIEW");

    const gateStep = steps.find((s) => s.key === "RISK_GATE")!;
    expect(gateStep.status).toBe("VETOED");
  });

  it("distinguishes MOCK scenarios from real exchange execution (execution_status=NOT_SENT)", () => {
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

  it("enforces order_permission=false and execution_authority=false on service assessments", () => {
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
    expect(RECORDED_SERVICE_ASSESSMENTS.excess_notional.assessment).toBe("HALT");
    expect(RECORDED_SERVICE_ASSESSMENTS.excess_notional.reasons).toContain(
      "excess_order_notional"
    );
  });

  it("keeps public View-Only Judge Mode locked when server admin secrets are unset or mismatched", () => {
    const reqWithoutHeader = new Request("http://localhost:3000/api/agent/start", {
      method: "POST",
    });
    const check = isAdminAuthorized(reqWithoutHeader);
    expect(check.authorized).toBe(false);
    expect([401, 503]).toContain(check.statusCode);
  });

  it("maps deterministic rule IDs to human-readable explanations", () => {
    const stale = explainRiskReason("stale_feed");
    expect(stale.ruleId).toBe("stale_feed");
    expect(stale.title).toContain("Stale");

    const unknownOrder = explainRiskReason("unresolved_prior_order");
    expect(unknownOrder.ruleId).toBe("unresolved_prior_order");
    expect(unknownOrder.title).toContain("Unresolved Prior Order");
  });
});
