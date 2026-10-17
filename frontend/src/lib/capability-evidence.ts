import type { Capability } from "./types";

const object = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);

// Diagnostics prove observed response behavior only, never execution authority.
export function diagnosticCapabilities(report: unknown, now = Date.now()): Record<string, Capability> {
  if (!object(report) || !object(report.capabilities) || !Array.isArray(report.events)) return {};
  const result: Record<string, Capability> = {};
  for (const [key, operation] of [["EVREN_STRUCTURED_OUTPUT", "EVREN:probe_structured_output"], ["EVREN_TOOL_CALLING", "EVREN:probe_tool_calling"]]) {
    const cap = report.capabilities[key];
    if (!object(cap) || typeof cap.checked_at !== "string" || !Array.isArray(cap.evidence) || !cap.evidence.every(id => typeof id === "string")) continue;
    const age = now - Date.parse(cap.checked_at);
    if (!Number.isFinite(age) || age < -2000 || age > 15 * 60_000) continue;
    const evidence = cap.evidence;
    const matched = report.events.some(event => {
      if (!object(event) || !object(event.details) || !object(event.details.tool_call)) return false;
      const call = event.details.tool_call;
      return typeof call.evidence_id === "string" && evidence.includes(call.evidence_id) && call.tool_id === operation &&
        (cap.status === "FAIL" || call.success === true && typeof call.response_hash === "string" && /^[a-f\d]{64}$/i.test(call.response_hash));
    });
    if (matched && (cap.status === "PASS" || cap.status === "FAIL")) result[key] = {
      status: cap.status, checked_at: cap.checked_at,
      evidence: [...cap.evidence, `Recorded diagnostic; model=${String(report.model)}; returned tools never executed`],
    };
  }
  return result;
}
