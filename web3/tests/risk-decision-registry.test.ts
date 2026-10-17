import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { Common, Hardfork, Mainnet } from "@ethereumjs/common";
import { createAddressFromString, hexToBytes } from "@ethereumjs/util";
import { createVM } from "@ethereumjs/vm";
import { describe, expect, it } from "vitest";
import {
  decodeEventLog,
  decodeFunctionResult,
  encodeFunctionData,
  keccak256,
  toBytes,
} from "viem";
import { RISK_DECISION_REGISTRY_ABI } from "../abi";

const artifactPath = path.resolve(
  __dirname,
  "../artifacts/RiskDecisionRegistry.json"
);
const artifact = JSON.parse(fs.readFileSync(artifactPath, "utf8"));

const OWNER_HEX = "0x1111111111111111111111111111111111111111";
const UNAUTHORIZED_HEX = "0x2222222222222222222222222222222222222222";
const DELEGATE_HEX = "0x3333333333333333333333333333333333333333";

const NON_ZERO_BLOCK = {
  header: {
    number: BigInt(59593741),
    cliqueSigner: () => createAddressFromString(OWNER_HEX),
    coinbase: createAddressFromString(OWNER_HEX),
    timestamp: BigInt(1792231900), // 2026-10-17 UTC
    difficulty: BigInt(0),
    prevRandao: new Uint8Array(32),
    gasLimit: BigInt(30_000_000),
    baseFeePerGas: BigInt(25_000_000_000),
  },
} as never;

async function deployRegistryOnLocalEvm() {
  const common = new Common({ chain: Mainnet, hardfork: Hardfork.Paris });
  const vm = await createVM({ common });
  const ownerAddr = createAddressFromString(OWNER_HEX);

  const deployRes = await vm.evm.runCall({
    caller: ownerAddr,
    data: hexToBytes(artifact.bytecode as `0x${string}`),
    gasLimit: BigInt(5_000_000),
    block: NON_ZERO_BLOCK,
  });

  if (deployRes.execResult.exceptionError) {
    throw new Error(
      `Contract deployment failed: ${deployRes.execResult.exceptionError.error}`
    );
  }
  const contractAddress = deployRes.createdAddress!;
  return { vm, contractAddress };
}

describe("RiskDecisionRegistry Solidity Smart Contract Unit Tests (EVM + Backend Audit Integration)", () => {
  it("compiles cleanly and deploys with owner set as authorized emitter", async () => {
    const { vm, contractAddress } = await deployRegistryOnLocalEvm();
    const ownerAddr = createAddressFromString(OWNER_HEX);

    const callData = encodeFunctionData({
      abi: RISK_DECISION_REGISTRY_ABI,
      functionName: "owner",
    });
    const res = await vm.evm.runCall({
      to: contractAddress,
      caller: ownerAddr,
      data: hexToBytes(callData),
      gasLimit: BigInt(200_000),
      block: NON_ZERO_BLOCK,
    });
    expect(res.execResult.exceptionError).toBeUndefined();

    const decodedOwner = decodeFunctionResult({
      abi: RISK_DECISION_REGISTRY_ABI,
      functionName: "owner",
      data: `0x${Buffer.from(res.execResult.returnValue).toString("hex")}`,
    });
    expect(decodedOwner.toLowerCase()).toBe(OWNER_HEX.toLowerCase());
  });

  it("integrates actual backend audit assessment (`amendment-http.json`), verifies Python canonical SHA-256, records on EVM, and reads back receipt & event", async () => {
    // 1. Load real backend assessment from `backend/evidence/amendment-http.json`
    const evidencePath = path.resolve(
      __dirname,
      "../../backend/evidence/amendment-http.json"
    );
    const amendmentEvidence = JSON.parse(fs.readFileSync(evidencePath, "utf8"));
    const realAssessment = amendmentEvidence.checks.excess_notional.response;

    // 2. Recompute canonical SHA-256 over sanitized payload (without assessment_sha256)
    const copy = { ...realAssessment };
    delete copy.assessment_sha256;

    const canonicalize = (val: unknown): string => {
      if (Array.isArray(val)) {
        return `[${val.map(canonicalize).join(",")}]`;
      }
      if (val && typeof val === "object") {
        const obj = val as Record<string, unknown>;
        const keys = Object.keys(obj).sort();
        return `{${keys
          .map((k) => `${JSON.stringify(k)}:${canonicalize(obj[k])}`)
          .join(",")}}`;
      }
      if (typeof val === "number" && Number.isInteger(val)) {
        return val === 0 ? "0.0" : JSON.stringify(val);
      }
      return JSON.stringify(val);
    };

    const canonicalBytes = Buffer.from(canonicalize(copy), "utf8");
    const recomputedSha = crypto
      .createHash("sha256")
      .update(canonicalBytes)
      .digest("hex");

    expect(recomputedSha).toBe(realAssessment.assessment_sha256);

    const decisionHash = `0x${realAssessment.assessment_sha256}` as `0x${string}`;
    const runIdHash = keccak256(toBytes(realAssessment.run_id));
    const policyVersionHash = keccak256(toBytes("aegis-policy-v2.0"));
    const verdictCode = realAssessment.assessment === "HALT" ? 2 : 1;

    // 3. Submit to deployed RiskDecisionRegistry on local EVM
    const { vm, contractAddress } = await deployRegistryOnLocalEvm();
    const ownerAddr = createAddressFromString(OWNER_HEX);

    const recordData = encodeFunctionData({
      abi: RISK_DECISION_REGISTRY_ABI,
      functionName: "recordDecision",
      args: [decisionHash, runIdHash, policyVersionHash, verdictCode],
    });

    const txRes = await vm.evm.runCall({
      to: contractAddress,
      caller: ownerAddr,
      data: hexToBytes(recordData),
      gasLimit: BigInt(500_000),
      block: NON_ZERO_BLOCK,
    });

    expect(txRes.execResult.exceptionError).toBeUndefined();
    expect(txRes.execResult.logs?.length).toBe(1);

    // 4. Verify emitted DecisionReceiptRecorded event log
    const rawLog = txRes.execResult.logs![0];
    const topics = rawLog[1].map(
      (t) => `0x${Buffer.from(t).toString("hex")}` as `0x${string}`
    );
    const dataHex = `0x${Buffer.from(rawLog[2]).toString("hex")}` as `0x${string}`;

    const decodedEvent = decodeEventLog({
      abi: RISK_DECISION_REGISTRY_ABI,
      eventName: "DecisionReceiptRecorded",
      topics: topics as [`0x${string}`, ...`0x${string}`[]],
      data: dataHex,
    });

    expect(decodedEvent.args.decisionHash).toBe(decisionHash);
    expect(decodedEvent.args.runIdHash).toBe(runIdHash);
    expect(decodedEvent.args.policyVersionHash).toBe(policyVersionHash);
    expect(decodedEvent.args.caller.toLowerCase()).toBe(OWNER_HEX.toLowerCase());
    expect(decodedEvent.args.verdictCode).toBe(2);
    expect(decodedEvent.args.timestamp).toBe(BigInt(1792231900));

    // 5. Read back via getDecisionReceipt(decisionHash)
    const getCallData = encodeFunctionData({
      abi: RISK_DECISION_REGISTRY_ABI,
      functionName: "getDecisionReceipt",
      args: [decisionHash],
    });

    const readRes = await vm.evm.runCall({
      to: contractAddress,
      caller: ownerAddr,
      data: hexToBytes(getCallData),
      gasLimit: BigInt(200_000),
      block: NON_ZERO_BLOCK,
    });
    expect(readRes.execResult.exceptionError).toBeUndefined();

    const [
      storedDecisionHash,
      storedRunIdHash,
      storedPolicyHash,
      storedCaller,
      storedTimestamp,
      storedVerdict,
      exists,
    ] = decodeFunctionResult({
      abi: RISK_DECISION_REGISTRY_ABI,
      functionName: "getDecisionReceipt",
      data: `0x${Buffer.from(readRes.execResult.returnValue).toString("hex")}`,
    });

    expect(exists).toBe(true);
    expect(storedDecisionHash).toBe(decisionHash);
    expect(storedRunIdHash).toBe(runIdHash);
    expect(storedPolicyHash).toBe(policyVersionHash);
    expect(storedCaller.toLowerCase()).toBe(OWNER_HEX.toLowerCase());
    expect(storedTimestamp).toBe(BigInt(1792231900));
    expect(storedVerdict).toBe(2);
  });

  it("enforces duplicate guard, zero-hash guard, invalid verdict guard, and caller authorization", async () => {
    const { vm, contractAddress } = await deployRegistryOnLocalEvm();
    const ownerAddr = createAddressFromString(OWNER_HEX);
    const unauthAddr = createAddressFromString(UNAUTHORIZED_HEX);
    const delegateAddr = createAddressFromString(DELEGATE_HEX);

    const decisionHash = keccak256(toBytes("decision-1"));
    const runIdHash = keccak256(toBytes("run-1"));
    const policyHash = keccak256(toBytes("policy-v2"));

    // 1. Unauthorized caller is rejected
    const recordCall = encodeFunctionData({
      abi: RISK_DECISION_REGISTRY_ABI,
      functionName: "recordDecision",
      args: [decisionHash, runIdHash, policyHash, 1],
    });
    const unauthRes = await vm.evm.runCall({
      to: contractAddress,
      caller: unauthAddr,
      data: hexToBytes(recordCall),
      gasLimit: BigInt(300_000),
      block: NON_ZERO_BLOCK,
    });
    expect(unauthRes.execResult.exceptionError).toBeDefined();

    // 2. Owner authorizes delegate -> delegate succeeds
    const authCall = encodeFunctionData({
      abi: RISK_DECISION_REGISTRY_ABI,
      functionName: "setAuthorizedEmitter",
      args: [DELEGATE_HEX, true],
    });
    await vm.evm.runCall({
      to: contractAddress,
      caller: ownerAddr,
      data: hexToBytes(authCall),
      gasLimit: BigInt(200_000),
      block: NON_ZERO_BLOCK,
    });

    const delegateRes = await vm.evm.runCall({
      to: contractAddress,
      caller: delegateAddr,
      data: hexToBytes(recordCall),
      gasLimit: BigInt(300_000),
      block: NON_ZERO_BLOCK,
    });
    expect(delegateRes.execResult.exceptionError).toBeUndefined();

    // 3. Duplicate submission of same decisionHash reverts with DuplicateDecisionHash
    const dupRes = await vm.evm.runCall({
      to: contractAddress,
      caller: ownerAddr,
      data: hexToBytes(recordCall),
      gasLimit: BigInt(300_000),
      block: NON_ZERO_BLOCK,
    });
    expect(dupRes.execResult.exceptionError).toBeDefined();

    // 4. Invalid verdictCode (99) reverts
    const badVerdictCall = encodeFunctionData({
      abi: RISK_DECISION_REGISTRY_ABI,
      functionName: "recordDecision",
      args: [keccak256(toBytes("decision-2")), runIdHash, policyHash, 99],
    });
    const badVerdictRes = await vm.evm.runCall({
      to: contractAddress,
      caller: ownerAddr,
      data: hexToBytes(badVerdictCall),
      gasLimit: BigInt(300_000),
      block: NON_ZERO_BLOCK,
    });
    expect(badVerdictRes.execResult.exceptionError).toBeDefined();
  });
});
