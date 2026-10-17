/** Read-only verification/export of an ERC-8004 registration already signed in MetaMask. */
import { readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { parseArgs } from "node:util";
import { createPublicClient, http, type Hex } from "viem";
import { avalancheFuji } from "viem/chains";
import { verifyRegistration } from "../../frontend/src/lib/fuji-identity";
import { FUJI_RPC } from "../../frontend/src/lib/fuji-wallet";
import { ERC8004_REPUTATION_REGISTRY_ABI, OFFICIAL_FUJI_ERC8004_REPUTATION_REGISTRY } from "../abi";

async function main() {
  const { values } = parseArgs({ options: { tx: { type: "string" } } });
  if (!values.tx || !/^0x[\da-f]{64}$/i.test(values.tx)) throw new Error("Supply the actual --tx hash. This script never signs or registers.");
  const client = createPublicClient({ chain: avalancheFuji, transport: http(process.env.FUJI_RPC_URL || FUJI_RPC, { timeout: 10_000, retryCount: 0 }) });
  const verified = await verifyRegistration(client, values.tx as Hex);
  const path = resolve(__dirname, "../registration-proof.json");
  const previous = JSON.parse(await readFile(path, "utf8").catch(() => "null"));
  if (previous?.verified && previous.agentId !== verified.agentId) throw new Error("Existing verified identity differs; refusing overwrite.");
  let reputation: { status: string; feedback_count: string | null; summary_display: string } = { status: "UNAVAILABLE", feedback_count: null, summary_display: "Independent reputation read unavailable" };
  try {
    const clients = await client.readContract({ address: OFFICIAL_FUJI_ERC8004_REPUTATION_REGISTRY, abi: ERC8004_REPUTATION_REGISTRY_ABI, functionName: "getClients", args: [BigInt(verified.agentId)] });
    if (clients.length === 0) reputation = { status: "PASS", feedback_count: "0", summary_display: "No independent feedback yet" };
    else {
      const [count] = await client.readContract({ address: OFFICIAL_FUJI_ERC8004_REPUTATION_REGISTRY, abi: ERC8004_REPUTATION_REGISTRY_ABI, functionName: "getSummary", args: [BigInt(verified.agentId), clients, "", ""] });
      reputation = { status: "PASS", feedback_count: count.toString(), summary_display: `${count.toString()} independent feedback entries` };
    }
  } catch { /* Record unavailable without inventing zero or creating feedback. */ }
  const proof = { ...verified, timestamp: verified.checkedAt, reputationRegistryAddress: OFFICIAL_FUJI_ERC8004_REPUTATION_REGISTRY, reputation, private_key_loaded: false, writes_attempted_by_verifier: 0, measured_confirmation_ms: null, timing_note: "Post-confirmation independent verification; no confirmation latency claimed." };
  await writeFile(path, JSON.stringify(proof, null, 2) + "\n");
  console.log(JSON.stringify({ status: "PASS", agent_id: proof.agentId, owner: proof.owner, uri: proof.agentURI, transaction_hash: proof.registrationTxHash, block_number: proof.blockNumber, fee_wei: proof.fee_wei, reputation: proof.reputation }));
}
main().catch((error: unknown) => {
  // This verifier loads only public RPC data; omit RPC request/response bodies.
  const message = error instanceof Error ? ((error as Error & { shortMessage?: string }).shortMessage ?? error.message).split("\n")[0].slice(0, 240) : "Unknown verification error";
  console.error(JSON.stringify({ status: "FAIL", writes_attempted: 0, error: error instanceof Error ? error.name : "UnknownError", message }));
  process.exitCode = 1;
});
