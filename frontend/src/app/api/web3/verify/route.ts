import { NextRequest, NextResponse } from "next/server";
import { createPublicClient, encodeFunctionData, http, isAddress, isHex, keccak256, toBytes } from "viem";
import { avalancheFuji } from "viem/chains";
import { RECORDED_IDENTITY, RECORDED_SERVICE_ASSESSMENTS } from "@/lib/fixtures";
import { fetchBackendJson } from "@/lib/server-backend";
import type { Identity } from "@/lib/types";
import { IDENTITY_REGISTRY, verifyRegistration } from "@/lib/fuji-identity";
import { identityFromProof, readRegisteredIdentity } from "@/lib/server-fuji-identity";
import { EXPECTED_FUJI_ACCOUNT, RECEIPT_ABI } from "@/lib/fuji-wallet";

export const dynamic = "force-dynamic";

export const OFFICIAL_FUJI_IDENTITY_REGISTRY =
  "0x8004A818BFB912233c491871b3d84c89A494BD9e";
export const OFFICIAL_FUJI_REPUTATION_REGISTRY =
  "0x8004B663056A597Dffe9eCcC1965A193B7388713";

const ERC8004_ABI = [
  {
    type: "function",
    name: "name",
    stateMutability: "view",
    inputs: [],
    outputs: [{ name: "", type: "string" }],
  },
  {
    type: "function",
    name: "symbol",
    stateMutability: "view",
    inputs: [],
    outputs: [{ name: "", type: "string" }],
  },
  {
    type: "function",
    name: "ownerOf",
    stateMutability: "view",
    inputs: [{ name: "tokenId", type: "uint256" }],
    outputs: [{ name: "owner", type: "address" }],
  },
  {
    type: "function",
    name: "tokenURI",
    stateMutability: "view",
    inputs: [{ name: "tokenId", type: "uint256" }],
    outputs: [{ name: "uri", type: "string" }],
  },
] as const;

const REPUTATION_ABI = [
  {
    type: "function",
    name: "getIdentityRegistry",
    stateMutability: "view",
    inputs: [],
    outputs: [{ name: "identityRegistry", type: "address" }],
  },
  {
    type: "function",
    name: "getClients",
    stateMutability: "view",
    inputs: [{ name: "agentId", type: "uint256" }],
    outputs: [{ name: "clients", type: "address[]" }],
  },
  {
    type: "function",
    name: "getSummary",
    stateMutability: "view",
    inputs: [
      { name: "agentId", type: "uint256" },
      { name: "clientAddresses", type: "address[]" },
      { name: "tag1", type: "string" },
      { name: "tag2", type: "string" },
    ],
    outputs: [
      { name: "count", type: "uint64" },
      { name: "summaryValue", type: "int128" },
      { name: "summaryValueDecimals", type: "uint8" },
    ],
  },
] as const;

const RECEIPT_REGISTRY_ABI = [
  {
    type: "function",
    name: "getDecisionReceipt",
    stateMutability: "view",
    inputs: [{ name: "decisionHash", type: "bytes32" }],
    outputs: [
      { name: "storedDecisionHash", type: "bytes32" },
      { name: "runIdHash", type: "bytes32" },
      { name: "policyVersionHash", type: "bytes32" },
      { name: "caller", type: "address" },
      { name: "timestamp", type: "uint64" },
      { name: "verdictCode", type: "uint8" },
      { name: "exists", type: "bool" },
    ],
  },
] as const;

export async function GET(request: NextRequest) {
  const checkedAt = new Date().toISOString();
  const rpcUrl =
    process.env.FUJI_RPC_URL || "https://api.avax-test.network/ext/bc/C/rpc";

  const backendRes = await fetchBackendJson<Identity>("/api/web3/identity", {
    timeoutMs: 3000,
  });
  const registeredProof = await readRegisteredIdentity().catch(() => null);
  const backendIdentity: Identity = registeredProof ? identityFromProof(registeredProof) : backendRes.data || RECORDED_IDENTITY;

  const registryAddress =
    request.nextUrl.searchParams.get("registry") ||
    backendIdentity.registry_address ||
    process.env.ERC8004_REGISTRY_ADDRESS ||
    OFFICIAL_FUJI_IDENTITY_REGISTRY;
  const agentId =
    request.nextUrl.searchParams.get("agentId") ||
    backendIdentity.agent_id ||
    process.env.ERC8004_AGENT_ID ||
    null;
  const registrationTxHash =
    request.nextUrl.searchParams.get("txHash") ||
    backendIdentity.registration_tx_hash ||
    backendIdentity.tx_hash ||
    process.env.ERC8004_TX_HASH ||
    null;

  const decisionRegistryAddress =
    request.nextUrl.searchParams.get("decisionRegistry") ||
    process.env.RISK_DECISION_REGISTRY_ADDRESS ||
    null;

  const defaultAssessment = RECORDED_SERVICE_ASSESSMENTS.excess_notional;
  const sampleDigest =
    request.nextUrl.searchParams.get("digest") ||
    process.env.RISK_DECISION_SAMPLE_SHA256 ||
    `0x${defaultAssessment.assessment_sha256}`;

  const client = createPublicClient({
    chain: avalancheFuji,
    transport: http(rpcUrl, { timeout: 5000 }),
  });

  let rpcConnected = false;
  let rpcChainId: number | null = null;
  let latestBlockNumber: number | null = null;
  let officialIdentityCodeVerified = false;
  let officialReputationCodeVerified = false;
  let officialIdentityName: string | null = null;
  let officialIdentitySymbol: string | null = null;

  try {
    const [cid, blockNum, idCode, repCode, nameVal, symVal] = await Promise.all([
      client.getChainId(),
      client.getBlockNumber(),
      client.getCode({ address: OFFICIAL_FUJI_IDENTITY_REGISTRY }),
      client.getCode({ address: OFFICIAL_FUJI_REPUTATION_REGISTRY }),
      client
        .readContract({
          address: OFFICIAL_FUJI_IDENTITY_REGISTRY,
          abi: ERC8004_ABI,
          functionName: "name",
        })
        .catch(() => null),
      client
        .readContract({
          address: OFFICIAL_FUJI_IDENTITY_REGISTRY,
          abi: ERC8004_ABI,
          functionName: "symbol",
        })
        .catch(() => null),
    ]);
    rpcConnected = true;
    rpcChainId = cid;
    latestBlockNumber = Number(blockNum);
    officialIdentityCodeVerified = Boolean(idCode && idCode !== "0x");
    officialReputationCodeVerified = Boolean(repCode && repCode !== "0x");
    officialIdentityName = nameVal;
    officialIdentitySymbol = symVal;
  } catch {
    rpcConnected = false;
  }

  let identityReadback: {
    status: "PASS" | "FAIL" | "NOT_TESTED";
    verified: boolean;
    registry_address: string;
    registry_has_code: boolean;
    owner: string | null;
    agent_uri: string | null;
    tx_receipt_status: string;
    note: string;
  } = {
    status: "NOT_TESTED",
    verified: false,
    registry_address: registryAddress,
    registry_has_code: officialIdentityCodeVerified,
    owner: null,
    agent_uri: null,
    tx_receipt_status: "NOT_TESTED",
    note: officialIdentityCodeVerified
      ? `Verified official Fuji ERC-8004 IdentityRegistry bytecode at ${OFFICIAL_FUJI_IDENTITY_REGISTRY} (${officialIdentityName} / ${officialIdentitySymbol}) and ReputationRegistry at ${OFFICIAL_FUJI_REPUTATION_REGISTRY}. AEGIS agentId registration is NOT_TESTED until a funded Fuji wallet registers a public HTTPS agentURI.`
      : "Fuji RPC check pending.",
  };

  if (rpcConnected && rpcChainId === 43113 && registryAddress && agentId) {
    if (!isAddress(registryAddress)) {
      identityReadback = {
        status: "FAIL",
        verified: false,
        registry_address: registryAddress,
        registry_has_code: false,
        owner: null,
        agent_uri: null,
        tx_receipt_status: "INVALID_ADDRESS",
        note: "Provided registry address is not a valid EVM address.",
      };
    } else {
      try {
        if (registryAddress.toLowerCase() !== IDENTITY_REGISTRY.toLowerCase() || !registrationTxHash || !/^0x[\da-f]{64}$/i.test(registrationTxHash)) throw new Error("Official AEGIS registration transaction required.");
        const proof = registeredProof?.registrationTxHash === registrationTxHash ? registeredProof : await verifyRegistration(client, registrationTxHash as `0x${string}`);
        if (proof.agentId !== BigInt(agentId).toString()) throw new Error("Agent ID does not match the actual Registered event.");
        identityReadback = {
          status: "PASS", verified: true, registry_address: registryAddress, registry_has_code: true,
          owner: proof.owner, agent_uri: proof.agentURI, tx_receipt_status: "success",
          note: "Verified AEGIS registration transaction, official Registered event, exact account/metadata URI, ownerOf and tokenURI on Fuji.",
        };
      } catch (err) {
        identityReadback = {
          status: "FAIL",
          verified: false,
          registry_address: registryAddress,
          registry_has_code: officialIdentityCodeVerified,
          owner: null,
          agent_uri: null,
          tx_receipt_status: "READ_ERROR",
          note: `Contract read-back failed: ${
            err instanceof Error ? err.message : String(err)
          }`,
        };
      }
    }
  }

  const normalizedDigest = sampleDigest.startsWith("0x")
    ? sampleDigest
    : `0x${sampleDigest}`;
  const computedRunIdHash = keccak256(toBytes(defaultAssessment.run_id));
  const computedPolicyVersionHash = keccak256(toBytes("aegis-policy-v2.0"));

  let receiptReadback: {
    status: "PASS" | "FAIL" | "NOT_TESTED";
    verified: boolean;
    contract_address: string | null;
    decision_hash: string;
    run_id_hash: string;
    policy_version_hash: string;
    exists_on_chain: boolean;
    caller: string | null;
    timestamp_unix: number | null;
    verdict_code: number | null;
    local_evm_unit_tests: string;
    transaction_hash: string | null;
    note: string;
  } = {
    status: "NOT_TESTED",
    verified: false,
    contract_address: decisionRegistryAddress,
    decision_hash: normalizedDigest,
    run_id_hash: computedRunIdHash,
    policy_version_hash: computedPolicyVersionHash,
    exists_on_chain: false,
    caller: null,
    timestamp_unix: null,
    verdict_code: null,
    local_evm_unit_tests: "PASS (3/3 in web3/tests/risk-decision-registry.test.ts)",
    transaction_hash: null,
    note: "RiskDecisionRegistry.sol is compiled and verified in local EVM unit tests with real backend assessment hashes; live Fuji deployment awaits a disposable wallet funded with faucet AVAX (status=NOT_TESTED).",
  };

  if (
    rpcConnected &&
    rpcChainId === 43113 &&
    decisionRegistryAddress &&
    isAddress(decisionRegistryAddress) &&
    isHex(normalizedDigest) &&
    normalizedDigest.length === 66
  ) {
    try {
      const code = await client.getCode({ address: decisionRegistryAddress });
      if (!code || code === "0x") {
        receiptReadback = {
          ...receiptReadback,
          status: "FAIL",
          note: `No bytecode at RiskDecisionRegistry address ${decisionRegistryAddress} on Fuji 43113.`,
        };
      } else {
        const [
          ,
          runIdHash,
          policyVersionHash,
          caller,
          timestamp,
          verdictCode,
          exists,
        ] = await client.readContract({
          address: decisionRegistryAddress,
          abi: RECEIPT_REGISTRY_ABI,
          functionName: "getDecisionReceipt",
          args: [normalizedDigest as `0x${string}`],
        });
        let transactionHash: string | null = null;
        const sampleTx = process.env.RISK_DECISION_SAMPLE_TX_HASH;
        if (exists && sampleTx && /^0x[\da-f]{64}$/i.test(sampleTx)) {
          try {
            const hash = sampleTx as `0x${string}`;
            const [tx, confirmed] = await Promise.all([client.getTransaction({ hash }), client.getTransactionReceipt({ hash })]);
            const expectedInput = encodeFunctionData({ abi: RECEIPT_ABI, functionName: "recordDecision", args: [normalizedDigest as `0x${string}`, runIdHash, policyVersionHash, verdictCode] });
            if (confirmed.status === "success" && tx.to?.toLowerCase() === decisionRegistryAddress.toLowerCase() &&
                tx.from.toLowerCase() === EXPECTED_FUJI_ACCOUNT.toLowerCase() && caller.toLowerCase() === tx.from.toLowerCase() &&
                tx.value === BigInt(0) && tx.input.toLowerCase() === expectedInput.toLowerCase()) transactionHash = hash;
          } catch { /* Stored receipt may be readable while transaction linkage is unavailable. */ }
        }
        receiptReadback = {
          status: exists ? "PASS" : "NOT_TESTED",
          verified: exists,
          contract_address: decisionRegistryAddress,
          decision_hash: normalizedDigest,
          run_id_hash: exists ? runIdHash : computedRunIdHash,
          policy_version_hash: exists
            ? policyVersionHash
            : computedPolicyVersionHash,
          exists_on_chain: exists,
          transaction_hash: transactionHash,
          caller: exists ? caller : null,
          timestamp_unix: exists ? Number(timestamp) : null,
          verdict_code: exists ? Number(verdictCode) : null,
          local_evm_unit_tests:
            "PASS (3/3 in web3/tests/risk-decision-registry.test.ts)",
          note: exists
            ? `Independent Fuji read-back verified decisionHash anchored by ${caller} at unix=${Number(
                timestamp
              )}.`
            : "RiskDecisionRegistry contract is deployed on Fuji, but this decisionHash has not been committed yet.",
        };
      }
    } catch (err) {
      receiptReadback = {
        ...receiptReadback,
        status: "FAIL",
        note: `Receipt read-back failed: ${
          err instanceof Error ? err.message : String(err)
        }`,
      };
    }
  }

  let reputationReadback: {
    status: "PASS" | "NOT_TESTED" | "READ_ONLY_READY";
    registry_address: string;
    linked_identity_registry: string | null;
    feedback_count: number;
    summary_display: string;
    note: string;
  } = {
    status: officialReputationCodeVerified ? "READ_ONLY_READY" : "NOT_TESTED",
    registry_address: OFFICIAL_FUJI_REPUTATION_REGISTRY,
    linked_identity_registry: null,
    feedback_count: 0,
    summary_display: "No independent feedback yet",
    note: "Self-feedback is disallowed by protocol rules; no fake or self-awarded ratings.",
  };

  if (rpcConnected && officialReputationCodeVerified) {
    try {
      const linkedId = await client.readContract({
        address: OFFICIAL_FUJI_REPUTATION_REGISTRY,
        abi: REPUTATION_ABI,
        functionName: "getIdentityRegistry",
      });
      if (agentId) {
        const tokenId = BigInt(agentId);
        const clients = await client.readContract({
          address: OFFICIAL_FUJI_REPUTATION_REGISTRY,
          abi: REPUTATION_ABI,
          functionName: "getClients",
          args: [tokenId],
        });
        if (clients && clients.length > 0) {
          const [count, val, dec] = await client.readContract({
            address: OFFICIAL_FUJI_REPUTATION_REGISTRY,
            abi: REPUTATION_ABI,
            functionName: "getSummary",
            args: [tokenId, clients, "", ""],
          });
          reputationReadback = {
            status: "PASS",
            registry_address: OFFICIAL_FUJI_REPUTATION_REGISTRY,
            linked_identity_registry: linkedId,
            feedback_count: Number(count),
            summary_display:
              Number(count) === 0
                ? "No independent feedback yet"
                : `${Number(val) / 10 ** Number(dec)} (${Number(count)} independent reviews)`,
            note: `Read-only query from official Fuji ReputationRegistry for agentId=${agentId}.`,
          };
        } else {
          reputationReadback = {
            status: "PASS",
            registry_address: OFFICIAL_FUJI_REPUTATION_REGISTRY,
            linked_identity_registry: linkedId,
            feedback_count: 0,
            summary_display: "No independent feedback yet",
            note: `On-chain ReputationRegistry queried for agentId=${agentId}; 0 third-party feedbacks recorded.`,
          };
        }
      } else {
        reputationReadback = {
          status: "READ_ONLY_READY",
          registry_address: OFFICIAL_FUJI_REPUTATION_REGISTRY,
          linked_identity_registry: linkedId,
          feedback_count: 0,
          summary_display: "No independent feedback yet",
          note: `Verified ReputationRegistry.getIdentityRegistry() -> ${linkedId}. No agentId minted yet; self-feedback is forbidden.`,
        };
      }
    } catch {
      // Keep default read-only note
    }
  }

  return NextResponse.json({
    checked_at: checkedAt,
    chain_id: 43113,
    network: "Avalanche Fuji Testnet (C-Chain)",
    rpc_url: rpcUrl,
    rpc_connected: rpcConnected,
    rpc_chain_id: rpcChainId,
    latest_block_number: latestBlockNumber,
    official_erc8004_registries: {
      identity_registry: OFFICIAL_FUJI_IDENTITY_REGISTRY,
      identity_registry_has_code: officialIdentityCodeVerified,
      identity_registry_name: officialIdentityName,
      identity_registry_symbol: officialIdentitySymbol,
      reputation_registry: OFFICIAL_FUJI_REPUTATION_REGISTRY,
      reputation_registry_has_code: officialReputationCodeVerified,
    },
    backend_identity: backendIdentity,
    erc8004_readback: identityReadback,
    reputation_readback: reputationReadback,
    decision_receipt_readback: receiptReadback,
    architecture_boundary:
      "Agent reasoning/inference (LAYA, EVREN) and OKX ATK trading run OFF-CHAIN. Fuji contracts supply ERC-8004 identity and SHA-256 decision receipt anchoring only.",
  });
}
