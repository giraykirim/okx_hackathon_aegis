/** Read-only proof export for transactions explicitly signed by the operator in MetaMask. */
import { readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { parseArgs } from "node:util";
import { createPublicClient, http, type Hex } from "viem";
import { avalancheFuji } from "viem/chains";
import { buildFujiPlan } from "../../frontend/src/lib/fuji-plan";
import { FUJI_RPC, RECEIPT_ABI, verifyFujiTransaction } from "../../frontend/src/lib/fuji-wallet";

async function main() {
  const { values } = parseArgs({ options: {
    "deploy-tx": { type: "string" }, "record-tx": { type: "string" },
    output: { type: "string", default: "metamask-fuji-proof.json" },
  } });
  for (const hash of [values["deploy-tx"], values["record-tx"]].filter(Boolean)) {
    if (!/^0x[a-fA-F0-9]{64}$/.test(hash!)) throw new Error("Expected an actual Fuji transaction hash.");
  }
  if (!values["deploy-tx"]) throw new Error("--deploy-tx is required. This script never deploys or signs.");
  const root = resolve(__dirname, "../..");
  const artifact = JSON.parse(await readFile(resolve(root, "web3/artifacts/RiskDecisionRegistry.json"), "utf8"));
  const canonical = await readFile(resolve(root, "web3/artifacts/receipt-assessment.json"));
  const assessment = JSON.parse(await readFile(resolve(root, "backend/evidence/amendment-http.json"), "utf8")).checks.excess_notional.response;
  const plan = buildFujiPlan(artifact, canonical, assessment);
  const client = createPublicClient({ chain: avalancheFuji, transport: http(FUJI_RPC, { timeout: 10_000, retryCount: 0 }) });
  const deployment = await verifyFujiTransaction(client, plan, "deploy", values["deploy-tx"] as Hex);
  const record = values["record-tx"] ? await verifyFujiTransaction(client, plan, "record", values["record-tx"] as Hex, deployment.contract_address) : null;
  const stored = record ? await client.readContract({ address: deployment.contract_address, abi: RECEIPT_ABI, functionName: "getDecisionReceipt", args: [plan.decision_hash] }) : null;
  const proof = {
    recorded_at: new Date().toISOString(), chain_id: 43113,
    signing: "USER_METAMASK", private_key_loaded: false, writes_attempted_by_verifier: 0,
    deployment, receipt: record, plan,
    receipt_readback: stored ? {
      decisionHash: stored[0], runIdHash: stored[1], policyVersionHash: stored[2],
      caller: stored[3], timestamp: stored[4].toString(), verdictCode: stored[5], exists: stored[6],
    } : null,
    receipt_status: record ? "PASS" : "NOT_TESTED",
    erc8004_registration: "NOT_TESTED_NEEDS_PUBLIC_METADATA_AND_REGISTRATION",
    measured_confirmation_ms: null,
    timing_note: "Independent post-confirmation verification; no submission-to-confirmation latency claimed.",
  };
  await writeFile(resolve(values.output!), JSON.stringify(proof, null, 2) + "\n");
  console.log(JSON.stringify({ deployment: "PASS", receipt: record ? "PASS" : "NOT_TESTED", contract_address: deployment.contract_address, deploy_tx: deployment.transaction_hash, record_tx: record?.transaction_hash ?? null, output: values.output }));
}
main().catch(() => { console.error("Read-only Fuji verification failed; no transaction was sent. Check RPC availability, hashes and recorded artifacts."); process.exitCode = 1; });
