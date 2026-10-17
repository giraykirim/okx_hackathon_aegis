import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { createPublicClient, http, type Hex } from "viem";
import { avalancheFuji } from "viem/chains";
import { verifyRegistration, type RegistrationProof } from "./fuji-identity";
import { FUJI_RPC } from "./fuji-wallet";
import type { Identity } from "./types";

// Saved JSON selects a transaction only; verified=true always requires fresh RPC checks.
export async function readRegisteredIdentity(): Promise<RegistrationProof | null> {
  let hash = process.env.ERC8004_TX_HASH;
  if (!hash) {
    const saved = JSON.parse(await readFile(resolve(process.cwd(), "../web3/registration-proof.json"), "utf8").catch(() => "null"));
    hash = saved?.registrationTxHash;
  }
  if (!hash || !/^0x[\da-f]{64}$/i.test(hash)) return null;
  const client = createPublicClient({ chain: avalancheFuji, transport: http(process.env.FUJI_RPC_URL || FUJI_RPC, { timeout: 5000, retryCount: 0 }) });
  return verifyRegistration(client, hash as Hex);
}

export function identityFromProof(proof: RegistrationProof): Identity {
  return { chain_id: 43113, registry_address: proof.registryAddress, agent_id: proof.agentId, agent_uri: proof.agentURI, owner: proof.owner, registration_tx_hash: proof.registrationTxHash, tx_hash: proof.registrationTxHash, verified: true, verification_checked_at: proof.checkedAt, verification_status: proof.verification_status };
}
