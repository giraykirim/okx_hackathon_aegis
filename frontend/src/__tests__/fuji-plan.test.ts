import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { buildFujiPlan } from "../lib/fuji-plan";

const root = resolve(process.cwd(), "..");
const artifact = JSON.parse(readFileSync(resolve(root, "web3/artifacts/RiskDecisionRegistry.json"), "utf8"));
const recorded = JSON.parse(readFileSync(resolve(root, "backend/evidence/amendment-http.json"), "utf8")).checks.excess_notional.response;

// Match Python's already recorded serialization, including the float zero.
function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value && typeof value === "object") return `{${Object.entries(value).sort(([a], [b]) => a.localeCompare(b, "en")).map(([k, v]) => `${JSON.stringify(k)}:${canonical(v)}`).join(",")}}`;
  return value === 0 ? "0.0" : JSON.stringify(value);
}
const { assessment_sha256: digest, ...payload } = recorded;
const bytes = Buffer.from(canonical(payload));

describe("Unsigned Fuji deployment plan", () => {
  it("uses the actual compiled contract and byte-exact recorded backend digest", () => {
    const plan = buildFujiPlan(artifact, bytes, recorded);
    expect(plan.chain_id).toBe(43113);
    expect(plan.decision_hash).toBe(`0x${digest}`);
    expect(plan.verdict_code).toBe(2);
    expect(plan.bytecode).toBe(artifact.bytecode);
    expect(Object.keys(plan).some(k => /private|secret|balance/i.test(k))).toBe(false);
  });
  it("fails closed if the canonical proof bytes have changed", () => {
    expect(() => buildFujiPlan(artifact, Buffer.concat([bytes, Buffer.from(" ")]), recorded)).toThrow(/digest/i);
  });
  it("refuses a receipt that is presented as execution permission", () => {
    expect(() => buildFujiPlan(artifact, bytes, { ...recorded, assessment: "CLEAR_TO_PROCEED" })).toThrow();
  });
});
