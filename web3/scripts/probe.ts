/**
 * PROMPT 10 — `web3/scripts/probe.ts`
 * Verifies Avalanche Fuji (chainId == 43113), official ERC-8004 Identity & Reputation bytecode,
 * official registry read/simulate interface, and validates `web3/agent-registration.template.json`.
 */
import fs from "node:fs";
import path from "node:path";
import { createPublicClient, http } from "viem";
import { avalancheFuji } from "viem/chains";
import {
  ERC8004_IDENTITY_REGISTRY_ABI,
  ERC8004_REPUTATION_REGISTRY_ABI,
  FUJI_CHAIN_ID,
  FUJI_RPC_DEFAULT,
  OFFICIAL_FUJI_ERC8004_IDENTITY_REGISTRY,
  OFFICIAL_FUJI_ERC8004_REPUTATION_REGISTRY,
} from "../abi";

const ForbiddenSubstrings = [
  "localhost",
  "127.0.0.1",
  "0.0.0.0",
  "192.168.",
  "PRIVATE_KEY",
  "OKX_API",
  "EVREN_API",
];

export function validateAgentRegistrationJson(rawJson: string): {
  valid: boolean;
  errors: string[];
} {
  const errors: string[] = [];
  for (const forbidden of ForbiddenSubstrings) {
    if (rawJson.toLowerCase().includes(forbidden.toLowerCase())) {
      errors.push(`Forbidden substring detected in metadata: "${forbidden}"`);
    }
  }

  let parsed: Record<string, unknown>;
  try {
    parsed = JSON.parse(rawJson) as Record<string, unknown>;
  } catch (err) {
    return { valid: false, errors: [`Invalid JSON: ${(err as Error).message}`] };
  }

  if (parsed.type !== "https://eips.ethereum.org/EIPS/eip-8004#registration-v1") {
    errors.push("Field `type` must equal 'https://eips.ethereum.org/EIPS/eip-8004#registration-v1'");
  }
  if (parsed.name !== "AEGIS") {
    errors.push("Field `name` must equal 'AEGIS'");
  }
  if (typeof parsed.description !== "string" || !parsed.description.toLowerCase().includes("off-chain")) {
    errors.push("Field `description` must be a non-empty string explicitly stating off-chain runtime");
  }
  if (parsed.x402Support !== false) {
    errors.push("Field `x402Support` must be `false` unless x402 is genuinely implemented");
  }
  if (typeof parsed.active !== "boolean") {
    errors.push("Field `active` must be a boolean");
  }
  if (!Array.isArray(parsed.services)) {
    errors.push("Field `services` must be an array");
  } else {
    for (const svc of parsed.services) {
      const endpoint = (svc as { endpoint?: unknown })?.endpoint;
      if (typeof endpoint !== "string" || !endpoint.startsWith("https://")) {
        errors.push("Every entry in `services` must use a real public `https://` endpoint");
      }
    }
  }
  if (!Array.isArray(parsed.registrations)) {
    errors.push("Field `registrations` must be an array");
  }

  return { valid: errors.length === 0, errors };
}

async function main() {
  const rpcUrl = process.env.FUJI_RPC_URL?.trim() || FUJI_RPC_DEFAULT;
  const client = createPublicClient({
    chain: avalancheFuji,
    transport: http(rpcUrl, { timeout: 10_000 }),
  });

  // 1. Verify eth_chainId == 43113
  const chainId = await client.getChainId();
  if (chainId !== FUJI_CHAIN_ID) {
    throw new Error(`Expected chainId ${FUJI_CHAIN_ID}, received ${chainId}. Stopping.`);
  }
  const blockNumber = await client.getBlockNumber();

  // 2. Call getBytecode / getCode on Identity and Reputation contracts
  const [identityCode, reputationCode] = await Promise.all([
    client.getCode({ address: OFFICIAL_FUJI_ERC8004_IDENTITY_REGISTRY }),
    client.getCode({ address: OFFICIAL_FUJI_ERC8004_REPUTATION_REGISTRY }),
  ]);

  if (!identityCode || identityCode === "0x") {
    throw new Error(
      `STOP: IdentityRegistry (${OFFICIAL_FUJI_ERC8004_IDENTITY_REGISTRY}) has empty bytecode on Fuji.`
    );
  }
  if (!reputationCode || reputationCode === "0x") {
    throw new Error(
      `STOP: ReputationRegistry (${OFFICIAL_FUJI_ERC8004_REPUTATION_REGISTRY}) has empty bytecode on Fuji.`
    );
  }

  // 3. Test official ABI read & dry-run simulateContract for register(string agentURI)
  const [name, symbol, ownerOf1, tokenURI1, linkedIdentity] = await Promise.all([
    client.readContract({
      address: OFFICIAL_FUJI_ERC8004_IDENTITY_REGISTRY,
      abi: ERC8004_IDENTITY_REGISTRY_ABI,
      functionName: "name",
    }),
    client.readContract({
      address: OFFICIAL_FUJI_ERC8004_IDENTITY_REGISTRY,
      abi: ERC8004_IDENTITY_REGISTRY_ABI,
      functionName: "symbol",
    }),
    client.readContract({
      address: OFFICIAL_FUJI_ERC8004_IDENTITY_REGISTRY,
      abi: ERC8004_IDENTITY_REGISTRY_ABI,
      functionName: "ownerOf",
      args: [1n],
    }),
    client.readContract({
      address: OFFICIAL_FUJI_ERC8004_IDENTITY_REGISTRY,
      abi: ERC8004_IDENTITY_REGISTRY_ABI,
      functionName: "tokenURI",
      args: [1n],
    }),
    client.readContract({
      address: OFFICIAL_FUJI_ERC8004_REPUTATION_REGISTRY,
      abi: ERC8004_REPUTATION_REGISTRY_ABI,
      functionName: "getIdentityRegistry",
    }),
  ]);

  // Dry-run simulation of register(string agentURI) using official ABI (does not broadcast or spend gas)
  const simResult = await client.simulateContract({
    address: OFFICIAL_FUJI_ERC8004_IDENTITY_REGISTRY,
    abi: ERC8004_IDENTITY_REGISTRY_ABI,
    functionName: "register",
    args: ["https://example.org/agent-registration.json"],
    account: "0x9Dae1ef186770C059BD35ea2D23dA3a166712e04",
  });

  // 4. Validate `web3/agent-registration.template.json`
  const templatePath = path.resolve(__dirname, "../agent-registration.template.json");
  const rawTemplate = fs.readFileSync(templatePath, "utf-8");
  const validation = validateAgentRegistrationJson(rawTemplate);
  if (!validation.valid) {
    throw new Error(`Template validation failed: ${validation.errors.join("; ")}`);
  }

  console.log(
    JSON.stringify(
      {
        status: "PASS",
        probed_at: new Date().toISOString(),
        chain_id: chainId,
        block_number: Number(blockNumber),
        identity_registry: {
          address: OFFICIAL_FUJI_ERC8004_IDENTITY_REGISTRY,
          code_bytes: (identityCode.length - 2) / 2,
          name,
          symbol,
          sample_agent_1_owner: ownerOf1,
          sample_agent_1_uri: tokenURI1,
          register_dry_run_simulated_agent_id: simResult.result.toString(),
        },
        reputation_registry: {
          address: OFFICIAL_FUJI_ERC8004_REPUTATION_REGISTRY,
          code_bytes: (reputationCode.length - 2) / 2,
          linked_identity_registry: linkedIdentity,
        },
        template_schema_validation: validation,
      },
      null,
      2
    )
  );
}

if (require.main === module) {
  main().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}
