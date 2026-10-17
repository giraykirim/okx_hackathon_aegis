import { createHash } from "node:crypto";
import { keccak256, toBytes, type Hex } from "viem";
import { EXPECTED_FUJI_ACCOUNT, type FujiPlan } from "./fuji-wallet";

export function buildFujiPlan(
  artifact: { bytecode: string; deployedBytecode: string },
  canonicalBytes: Buffer,
  recorded: { assessment_sha256: string; assessment: string; run_id: string; source_mode: string; timestamp: string },
): FujiPlan & { assessment_source_mode: string; evaluated_at: string; policy_tag: string } {
  const digest = createHash("sha256").update(canonicalBytes).digest("hex");
  if (!/^[a-f0-9]{64}$/.test(recorded.assessment_sha256) || digest !== recorded.assessment_sha256) throw new Error("Canonical assessment digest mismatch.");
  const canonical = JSON.parse(canonicalBytes.toString("utf8"));
  if (recorded.assessment !== "HALT" || canonical.assessment !== "HALT" || canonical.execution_authority !== false || canonical.order_permission !== false || canonical.run_id !== recorded.run_id) throw new Error("Only the recorded advisory HALT sample may be anchored.");
  for (const code of [artifact.bytecode, artifact.deployedBytecode]) {
    if (!/^0x(?:[\da-f]{2})+$/i.test(code) || code.length > 40_000) throw new Error("Compiled registry artifact unavailable.");
  }
  return {
    chain_id: 43113,
    expected_account: EXPECTED_FUJI_ACCOUNT,
    bytecode: artifact.bytecode as Hex,
    runtime_bytecode: artifact.deployedBytecode as Hex,
    decision_hash: `0x${digest}`,
    run_id_hash: keccak256(toBytes(recorded.run_id)),
    policy_version_hash: keccak256(toBytes("aegis-policy-v2.0")),
    verdict_code: 2,
    evidence_source: "backend/evidence/amendment-http.json:checks.excess_notional.response",
    assessment_source_mode: recorded.source_mode,
    evaluated_at: recorded.timestamp,
    policy_tag: "aegis-policy-v2.0",
  };
}
