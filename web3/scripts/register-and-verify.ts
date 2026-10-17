/**
 * PROMPT 11 & 12 — `web3/scripts/register-and-verify.ts`
 * Idempotent ERC-8004 registration & verification script on Avalanche Fuji (43113).
 * - If already registered in `web3/registration-proof.json`, performs on-chain VERIFY only (never mints duplicates).
 * - Only performs an on-chain write when FUJI_TEST_WALLET_PRIVATE_KEY (or FUJI_PRIVATE_KEY) AND a public HTTPS
 *   AGENT_REGISTRATION_URI are explicitly configured and funded.
 * - Reads ReputationRegistry summary read-only ("No independent feedback yet" when count == 0).
 * - Saves `web3/registration-proof.json` with zero secrets and no fabricated tx hashes.
 */
import fs from "node:fs";
import path from "node:path";
import {
  createPublicClient,
  createWalletClient,
  decodeEventLog,
  formatEther,
  http,
  type Hex,
} from "viem";
import { privateKeyToAccount } from "viem/accounts";
import { avalancheFuji } from "viem/chains";
import {
  ERC8004_IDENTITY_REGISTRY_ABI,
  ERC8004_REPUTATION_REGISTRY_ABI,
  FUJI_CHAIN_ID,
  FUJI_EXPLORER_TX_BASE,
  FUJI_RPC_DEFAULT,
  OFFICIAL_FUJI_ERC8004_IDENTITY_REGISTRY,
  OFFICIAL_FUJI_ERC8004_REPUTATION_REGISTRY,
} from "../abi";
import { validateAgentRegistrationJson } from "./probe";

const PROOF_PATH = path.resolve(__dirname, "../registration-proof.json");
const TEMPLATE_PATH = path.resolve(__dirname, "../agent-registration.template.json");

function isValidPublicHttpsUri(uri: string | undefined): uri is string {
  if (!uri) return false;
  try {
    const parsed = new URL(uri);
    if (parsed.protocol !== "https:") return false;
    const host = parsed.hostname.toLowerCase();
    if (
      host === "localhost" ||
      host === "127.0.0.1" ||
      host === "0.0.0.0" ||
      host.endsWith(".local")
    ) {
      return false;
    }
    return true;
  } catch {
    return false;
  }
}

async function queryReputationSummary(
  publicClient: ReturnType<typeof createPublicClient>,
  agentId: bigint | null
) {
  if (agentId === null) {
    return {
      status: "READ_ONLY_READY",
      feedback_count: 0,
      summary_display: "No independent feedback yet",
      note: "Self-feedback is disallowed by protocol rules; no agentId minted yet.",
    };
  }
  try {
    const clients = await publicClient.readContract({
      address: OFFICIAL_FUJI_ERC8004_REPUTATION_REGISTRY,
      abi: ERC8004_REPUTATION_REGISTRY_ABI,
      functionName: "getClients",
      args: [agentId],
    });
    if (!clients || clients.length === 0) {
      return {
        status: "PASS",
        feedback_count: 0,
        summary_display: "No independent feedback yet",
        note: "On-chain ReputationRegistry queried; 0 third-party client feedbacks recorded.",
      };
    }
    const [count, summaryValue, decimals] = await publicClient.readContract({
      address: OFFICIAL_FUJI_ERC8004_REPUTATION_REGISTRY,
      abi: ERC8004_REPUTATION_REGISTRY_ABI,
      functionName: "getSummary",
      args: [agentId, clients, "", ""],
    });
    return {
      status: "PASS",
      feedback_count: Number(count),
      summary_display:
        Number(count) === 0
          ? "No independent feedback yet"
          : `${Number(summaryValue) / 10 ** Number(decimals)} (${Number(count)} independent reviews)`,
      note: "Read-only query from official Fuji ReputationRegistry.",
    };
  } catch (err) {
    return {
      status: "READ_ONLY_ERROR",
      feedback_count: 0,
      summary_display: "No independent feedback yet",
      note: `Reputation read-back note: ${(err as Error).message}`,
    };
  }
}

async function main() {
  const rpcUrl = process.env.FUJI_RPC_URL?.trim() || FUJI_RPC_DEFAULT;
  const rawPrivKey = (
    process.env.FUJI_TEST_WALLET_PRIVATE_KEY ||
    process.env.FUJI_PRIVATE_KEY ||
    ""
  ).trim();
  const registrationUri = (
    process.env.AGENT_REGISTRATION_URI ||
    process.env.AEGIS_PUBLIC_AGENT_URI ||
    ""
  ).trim();

  const publicClient = createPublicClient({
    chain: avalancheFuji,
    transport: http(rpcUrl, { timeout: 12_000 }),
  });

  // Step 1: Verify chainId == 43113 and registry bytecode != 0x
  const chainId = await publicClient.getChainId();
  if (chainId !== FUJI_CHAIN_ID) {
    throw new Error(`Wrong chainId ${chainId}; expected ${FUJI_CHAIN_ID}`);
  }
  const [identityCode, reputationCode] = await Promise.all([
    publicClient.getCode({ address: OFFICIAL_FUJI_ERC8004_IDENTITY_REGISTRY }),
    publicClient.getCode({ address: OFFICIAL_FUJI_ERC8004_REPUTATION_REGISTRY }),
  ]);
  if (!identityCode || identityCode === "0x") {
    throw new Error("Official IdentityRegistry bytecode missing on Fuji");
  }
  if (!reputationCode || reputationCode === "0x") {
    throw new Error("Official ReputationRegistry bytecode missing on Fuji");
  }

  // Step 7: Idempotent check — if `registration-proof.json` already has a verified agentId, VERIFY on-chain instead of minting duplicate
  if (fs.existsSync(PROOF_PATH)) {
    try {
      const existing = JSON.parse(fs.readFileSync(PROOF_PATH, "utf-8"));
      if (existing.verified === true && existing.agentId !== null) {
        const agentIdBig = BigInt(existing.agentId);
        const [ownerOnChain, uriOnChain] = await Promise.all([
          publicClient.readContract({
            address: OFFICIAL_FUJI_ERC8004_IDENTITY_REGISTRY,
            abi: ERC8004_IDENTITY_REGISTRY_ABI,
            functionName: "ownerOf",
            args: [agentIdBig],
          }),
          publicClient.readContract({
            address: OFFICIAL_FUJI_ERC8004_IDENTITY_REGISTRY,
            abi: ERC8004_IDENTITY_REGISTRY_ABI,
            functionName: "tokenURI",
            args: [agentIdBig],
          }),
        ]);
        const reputation = await queryReputationSummary(publicClient, agentIdBig);
        const updatedProof = {
          ...existing,
          owner: ownerOnChain,
          agentURI: uriOnChain,
          verified: true,
          verification_status: "VERIFIED_IDEMPOTENT_READBACK",
          checkedAt: new Date().toISOString(),
          reputation,
        };
        fs.writeFileSync(PROOF_PATH, JSON.stringify(updatedProof, null, 2) + "\n");
        console.log("Idempotent verification succeeded for existing agentId:", existing.agentId);
        return;
      }
    } catch {
      // Proceed if existing proof file is unparseable or unverified
    }
  }

  // Step 8: If no private key or no valid HTTPS URI, write honest NOT_TESTED proof and exit cleanly
  if (!rawPrivKey || !isValidPublicHttpsUri(registrationUri)) {
    const reputation = await queryReputationSummary(publicClient, null);
    const notTestedProof = {
      chainId: FUJI_CHAIN_ID,
      registryAddress: OFFICIAL_FUJI_ERC8004_IDENTITY_REGISTRY,
      reputationRegistryAddress: OFFICIAL_FUJI_ERC8004_REPUTATION_REGISTRY,
      agentId: null,
      owner: null,
      registrationTxHash: null,
      explorerUrl: null,
      agentURI: isValidPublicHttpsUri(registrationUri) ? registrationUri : null,
      timestamp: new Date().toISOString(),
      verified: false,
      verification_status: "NOT_TESTED",
      reason: !rawPrivKey
        ? "FUJI_TEST_WALLET_PRIVATE_KEY not configured locally. No on-chain write attempted; zero fabricated IDs or tx hashes."
        : "AGENT_REGISTRATION_URI must be a reachable public HTTPS URL (localhost is forbidden).",
      reputation,
    };
    fs.writeFileSync(PROOF_PATH, JSON.stringify(notTestedProof, null, 2) + "\n");
    console.log(JSON.stringify(notTestedProof, null, 2));
    return;
  }

  // Step 2: Validate public AGENT_REGISTRATION_URI resolves directly to valid ERC-8004 JSON
  const metaRes = await fetch(registrationUri, {
    headers: { Accept: "application/json" },
  });
  if (!metaRes.ok) {
    throw new Error(
      `AGENT_REGISTRATION_URI (${registrationUri}) returned HTTP ${metaRes.status}`
    );
  }
  const metaText = await metaRes.text();
  const metaValidation = validateAgentRegistrationJson(metaText);
  if (!metaValidation.valid) {
    throw new Error(
      `Hosted AGENT_REGISTRATION_URI failed ERC-8004 schema validation: ${metaValidation.errors.join("; ")}`
    );
  }

  // Check wallet balance
  const normalizedKey = (
    rawPrivKey.startsWith("0x") ? rawPrivKey : `0x${rawPrivKey}`
  ) as Hex;
  const account = privateKeyToAccount(normalizedKey);
  const balanceWei = await publicClient.getBalance({ address: account.address });

  if (balanceWei === 0n) {
    const reputation = await queryReputationSummary(publicClient, null);
    const noGasProof = {
      chainId: FUJI_CHAIN_ID,
      registryAddress: OFFICIAL_FUJI_ERC8004_IDENTITY_REGISTRY,
      reputationRegistryAddress: OFFICIAL_FUJI_ERC8004_REPUTATION_REGISTRY,
      agentId: null,
      owner: account.address,
      registrationTxHash: null,
      explorerUrl: null,
      agentURI: registrationUri,
      timestamp: new Date().toISOString(),
      verified: false,
      verification_status: "NOT_TESTED",
      reason: `Disposable Fuji test wallet ${account.address} has 0.0 AVAX. Fund via Fuji faucet before registering.`,
      reputation,
    };
    fs.writeFileSync(PROOF_PATH, JSON.stringify(noGasProof, null, 2) + "\n");
    console.log(JSON.stringify(noGasProof, null, 2));
    return;
  }

  // Step 3: Call register(string agentURI) and parse confirmed Registered(uint256 agentId, string agentURI, address owner) event
  const walletClient = createWalletClient({
    account,
    chain: avalancheFuji,
    transport: http(rpcUrl, { timeout: 15_000 }),
  });

  const t0 = Date.now();
  const txHash = await walletClient.writeContract({
    address: OFFICIAL_FUJI_ERC8004_IDENTITY_REGISTRY,
    abi: ERC8004_IDENTITY_REGISTRY_ABI,
    functionName: "register",
    args: [registrationUri],
  });
  const receipt = await publicClient.waitForTransactionReceipt({ hash: txHash });
  const measuredConfirmationMs = Date.now() - t0;

  if (receipt.status !== "success") {
    throw new Error(`Registration transaction ${txHash} reverted on Fuji`);
  }

  let extractedAgentId: bigint | null = null;
  for (const log of receipt.logs) {
    try {
      const decoded = decodeEventLog({
        abi: ERC8004_IDENTITY_REGISTRY_ABI,
        data: log.data,
        topics: log.topics,
      });
      if (decoded.eventName === "Registered") {
        extractedAgentId = decoded.args.agentId;
        break;
      }
    } catch {
      // Ignore non-matching logs
    }
  }

  if (extractedAgentId === null) {
    throw new Error(
      `Transaction ${txHash} succeeded but Registered(agentId, agentURI, owner) event was not found in logs`
    );
  }

  // Step 4: Read back ownerOf(agentId) and tokenURI(agentId) from on-chain registry
  const [ownerReadback, uriReadback] = await Promise.all([
    publicClient.readContract({
      address: OFFICIAL_FUJI_ERC8004_IDENTITY_REGISTRY,
      abi: ERC8004_IDENTITY_REGISTRY_ABI,
      functionName: "ownerOf",
      args: [extractedAgentId],
    }),
    publicClient.readContract({
      address: OFFICIAL_FUJI_ERC8004_IDENTITY_REGISTRY,
      abi: ERC8004_IDENTITY_REGISTRY_ABI,
      functionName: "tokenURI",
      args: [extractedAgentId],
    }),
  ]);

  const verified =
    ownerReadback.toLowerCase() === account.address.toLowerCase() &&
    uriReadback === registrationUri;

  // Step 5: Update local template registrations array with confirmed agentId and eip155:43113:<identity>
  if (verified && fs.existsSync(TEMPLATE_PATH)) {
    const templateObj = JSON.parse(fs.readFileSync(TEMPLATE_PATH, "utf-8"));
    templateObj.registrations = [
      {
        agentId: Number(extractedAgentId),
        agentRegistry: `eip155:${FUJI_CHAIN_ID}:${OFFICIAL_FUJI_ERC8004_IDENTITY_REGISTRY}`,
      },
    ];
    fs.writeFileSync(TEMPLATE_PATH, JSON.stringify(templateObj, null, 2) + "\n");
  }

  // Step 6: Save PUBLIC `web3/registration-proof.json`
  const reputation = await queryReputationSummary(publicClient, extractedAgentId);
  const feeAvax = formatEther(
    receipt.gasUsed * (receipt.effectiveGasPrice ?? 0n)
  );
  const proof = {
    chainId: FUJI_CHAIN_ID,
    registryAddress: OFFICIAL_FUJI_ERC8004_IDENTITY_REGISTRY,
    reputationRegistryAddress: OFFICIAL_FUJI_ERC8004_REPUTATION_REGISTRY,
    agentId: extractedAgentId.toString(),
    owner: ownerReadback,
    registrationTxHash: txHash,
    blockNumber: Number(receipt.blockNumber),
    measuredConfirmationMs,
    feeAvax,
    explorerUrl: `${FUJI_EXPLORER_TX_BASE}${txHash}`,
    agentURI: uriReadback,
    timestamp: new Date().toISOString(),
    verified,
    verification_status: verified ? "VERIFIED" : "FAILED_READBACK_MISMATCH",
    reputation,
  };

  fs.writeFileSync(PROOF_PATH, JSON.stringify(proof, null, 2) + "\n");
  console.log(JSON.stringify(proof, null, 2));
}

if (require.main === module) {
  main().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}
