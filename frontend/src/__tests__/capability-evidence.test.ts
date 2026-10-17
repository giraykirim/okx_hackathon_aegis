import { describe, expect, it } from "vitest";
import { diagnosticCapabilities } from "../lib/capability-evidence";

const now = Date.parse("2026-10-17T14:00:00Z");
const stamp = "2026-10-17T13:59:00Z";
const report = {
  model: "unit-model",
  capabilities: { EVREN_TOOL_CALLING: { status: "PASS", checked_at: stamp, evidence: ["unit-evidence"] } },
  events: [{ details: { tool_call: { evidence_id: "unit-evidence", tool_id: "EVREN:probe_tool_calling", success: true, response_hash: "a".repeat(64) } } }],
};
describe("Recorded integration diagnostics", () => {
  it("requires correlated successful tool evidence and marks diagnostic scope", () => {
    expect(diagnosticCapabilities(report, now).EVREN_TOOL_CALLING.evidence.join(" ")).toMatch(/diagnostic/i);
  });
  it("does not turn old, uncorrelated or failed evidence into current capability PASS", () => {
    expect(diagnosticCapabilities(report, now + 16 * 60_000)).toEqual({});
    expect(diagnosticCapabilities({ ...report, events: [] }, now)).toEqual({});
    expect(diagnosticCapabilities({ ...report, events: [{ details: { tool_call: { ...report.events[0].details.tool_call, success: false } } }] }, now)).toEqual({});
  });
  it("never imports execution/model-quality claims from a diagnostic document", () => {
    expect(diagnosticCapabilities({ ...report, capabilities: { ...report.capabilities, ATK_DEMO_ORDER_SUBMISSION: report.capabilities.EVREN_TOOL_CALLING } }, now)).not.toHaveProperty("ATK_DEMO_ORDER_SUBMISSION");
  });
});
