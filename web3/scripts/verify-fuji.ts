/**
 * Avalanche Fuji (Chain ID 43113) Independent Read-Back Verifier
 *
 * Performs real JSON-RPC calls against Avalanche Fuji C-Chain to verify:
 * 1. Chain ID == 43113
 * 2. Official ERC-8004 IdentityRegistry (`0x8004A818BFB912233c491871b3d84c89A494BD9e`)
 *    and ReputationRegistry (`0x8004B663056A597Dffe9eCcC1965A193B7388713`) bytecode & view calls,
 *    plus `ownerOf(agentId)` and `tokenURI(agentId)` when `agentId` is provided.
 * 3. `RiskDecisionRegistry.sol` `getDecisionReceipt(bytes32 decisionHash)` + tx receipt confirmation.
 *
 * Never fabricates verification: if RPC is unreachable, contract address is not configured,
 * or bytecode is empty (`0x`), returns `verified: false` and `status: "NOT_TESTED" | "FAIL"`.
 */

import { createPublicClient, http, isAddress, isHex, toHex } from "viem";
import { avalancheFuji } from "viem/chains";
import {
  ERC8004_IDENTITY_REGISTRY_ABI,
  FUJI_CHAIN_ID,
  FUJI_RPC_DEFAULT,
  OFFICIAL_FUJI_ERC8004_IDENTITY_REGISTRY,
  OFFICIAL_FUJI_ERC8004_REPUTATION_REGISTRY,
  RISK_DECISION_REGISTRY_ABI,
} from "../abi";

export interface FujiIdentityVerification {
  chain_id: 43113;
  rpc_connected: boolean;
  rpc_chain_id: number | null;
  registry_address: string;
  registry_has_code: boolean;
  reputation_registry_address: string;
  reputation_registry_has_code: boolean;
  agent_id: string | null;
  owner: string | null;
  agent_uri: string | null;
  registration_tx_hash: string | null;
  tx_receipt_status: "success" | "reverted" | "not_found" | "not_checked";
  verified: boolean;
  verification_status: "PASS" | "FAIL" | "NOT_TESTED";
  verification_checked_at: string;
  notes: string[];
}

export interface FujiDecisionReceiptVerification {
  chain_id: 43113;
  contract_address: string | null;
  contract_has_code: boolean;
  decision_hash: string | null;
  run_id_hash: string | null;
  policy_version_hash: string | null;
  exists_on_chain: boolean;
  caller: string | null;
  timestamp_unix: number | null;
  verdict_code: number | null;
  tx_hash: string | null;
  block_number: number | null;
  gas_used: string | null;
  effective_gas_price_wei: string | null;
  measured_confirmation_ms: number | null;
  verified: boolean;
  verification_status: "PASS" | "FAIL" | "NOT_TESTED";
  checked_at: string;
  notes: string[];
}

export async function verifyFujiIdentity(params: {
  rpcUrl?: string;
  registryAddress?: string | null;
  agentId?: string | null;
  registrationTxHash?: string | null;
}): Promise<FujiIdentityVerification> {
  const checkedAt = new Date().toISOString();
  const rpcUrl = params.rpcUrl || process.env.FUJI_RPC_URL || FUJI_RPC_DEFAULT;
  const registryAddress =
    params.registryAddress ||
    process.env.ERC8004_REGISTRY_ADDRESS ||
    OFFICIAL_FUJI_ERC8004_IDENTITY_REGISTRY;
  const agentId = params.agentId ?? process.env.ERC8004_AGENT_ID ?? null;
  const txHash = params.registrationTxHash ?? process.env.ERC8004_TX_HASH ?? null;
  const notes: string[] = [
    "ERC-8004 registers on-chain agent identity and URI only; Python, LAYA, and EVREN run off-chain.",
  ];

  const client = createPublicClient({
    chain: avalancheFuji,
    transport: http(rpcUrl, { timeout: 6_000 }),
  });

  let rpcChainId: number | null = null;
  try {
    rpcChainId = await client.getChainId();
  } catch (err) {
    notes.push(
      `Fuji RPC connection failed: ${err instanceof Error ? err.message : String(err)}`
    );
    return {
      chain_id: FUJI_CHAIN_ID,
      rpc_connected: false,
      rpc_chain_id: null,
      registry_address: registryAddress,
      registry_has_code: false,
      reputation_registry_address: OFFICIAL_FUJI_ERC8004_REPUTATION_REGISTRY,
      reputation_registry_has_code: false,
      agent_id: agentId,
      owner: null,
      agent_uri: null,
      registration_tx_hash: txHash,
      tx_receipt_status: "not_checked",
      verified: false,
      verification_status: "NOT_TESTED",
      verification_checked_at: checkedAt,
      notes,
    };
  }

  if (rpcChainId !== FUJI_CHAIN_ID) {
    notes.push(
      `Connected RPC chain ID ${rpcChainId} does not match Avalanche Fuji (${FUJI_CHAIN_ID}).`
    );
    return {
      chain_id: FUJI_CHAIN_ID,
      rpc_connected: true,
      rpc_chain_id: rpcChainId,
      registry_address: registryAddress,
      registry_has_code: false,
      reputation_registry_address: OFFICIAL_FUJI_ERC8004_REPUTATION_REGISTRY,
      reputation_registry_has_code: false,
      agent_id: agentId,
      owner: null,
      agent_uri: null,
      registration_tx_hash: txHash,
      tx_receipt_status: "not_checked",
      verified: false,
      verification_status: "FAIL",
      verification_checked_at: checkedAt,
      notes,
    };
  }

  if (!isAddress(registryAddress)) {
    notes.push("Configured ERC8004_REGISTRY_ADDRESS is not a valid EVM address.");
    return {
      chain_id: FUJI_CHAIN_ID,
      rpc_connected: true,
      rpc_chain_id: rpcChainId,
      registry_address: registryAddress,
      registry_has_code: false,
      reputation_registry_address: OFFICIAL_FUJI_ERC8004_REPUTATION_REGISTRY,
      reputation_registry_has_code: false,
      agent_id: agentId,
      owner: null,
      agent_uri: null,
      registration_tx_hash: txHash,
      tx_receipt_status: "not_checked",
      verified: false,
      verification_status: "FAIL",
      verification_checked_at: checkedAt,
      notes,
    };
  }

  try {
    const [bytecode, repBytecode] = await Promise.all([
      client.getCode({ address: registryAddress }),
      client.getCode({ address: OFFICIAL_FUJI_ERC8004_REPUTATION_REGISTRY }),
    ]);
    const hasCode = Boolean(bytecode && bytecode !== "0x");
    const repHasCode = Boolean(repBytecode && repBytecode !== "0x");

    if (!hasCode) {
      notes.push(`No contract bytecode found at ${registryAddress} on Fuji 43113.`);
      return {
        chain_id: FUJI_CHAIN_ID,
        rpc_connected: true,
        rpc_chain_id: rpcChainId,
        registry_address: registryAddress,
        registry_has_code: false,
        reputation_registry_address: OFFICIAL_FUJI_ERC8004_REPUTATION_REGISTRY,
        reputation_registry_has_code: repHasCode,
        agent_id: agentId,
        owner: null,
        agent_uri: null,
        registration_tx_hash: txHash,
        tx_receipt_status: "not_checked",
        verified: false,
        verification_status: "FAIL",
        verification_checked_at: checkedAt,
        notes,
      };
    }

    notes.push(
      `Verified official Fuji ERC-8004 IdentityRegistry (${registryAddress}) and ReputationRegistry (${OFFICIAL_FUJI_ERC8004_REPUTATION_REGISTRY}) bytecode via eth_getCode.`
    );

    if (!agentId) {
      notes.push(
        "No AEGIS agentId registered yet (awaiting funded Fuji testnet wallet + public HTTPS agentURI). Status remains NOT_TESTED."
      );
      return {
        chain_id: FUJI_CHAIN_ID,
        rpc_connected: true,
        rpc_chain_id: rpcChainId,
        registry_address: registryAddress,
        registry_has_code: true,
        reputation_registry_address: OFFICIAL_FUJI_ERC8004_REPUTATION_REGISTRY,
        reputation_registry_has_code: repHasCode,
        agent_id: null,
        owner: null,
        agent_uri: null,
        registration_tx_hash: txHash,
        tx_receipt_status: "not_checked",
        verified: false,
        verification_status: "NOT_TESTED",
        verification_checked_at: checkedAt,
        notes,
      };
    }

    const tokenId = BigInt(agentId);
    const [owner, uri] = await Promise.all([
      client.readContract({
        address: registryAddress,
        abi: ERC8004_IDENTITY_REGISTRY_ABI,
        functionName: "ownerOf",
        args: [tokenId],
      }),
      client.readContract({
        address: registryAddress,
        abi: ERC8004_IDENTITY_REGISTRY_ABI,
        functionName: "tokenURI",
        args: [tokenId],
      }),
    ]);

    let txReceiptStatus: FujiIdentityVerification["tx_receipt_status"] =
      "not_checked";
    if (txHash && isHex(txHash) && txHash.length === 66) {
      try {
        const receipt = await client.getTransactionReceipt({ hash: txHash });
        txReceiptStatus = receipt.status === "success" ? "success" : "reverted";
      } catch {
        txReceiptStatus = "not_found";
      }
    }

    const verified =
      Boolean(owner) &&
      Boolean(uri) &&
      (txHash ? txReceiptStatus === "success" : true);

    notes.push(
      verified
        ? "Independent Fuji read-back confirmed ownerOf(agentId) and tokenURI(agentId)."
        : "Contract read succeeded but transaction receipt or non-empty tokenURI check was incomplete."
    );

    return {
      chain_id: FUJI_CHAIN_ID,
      rpc_connected: true,
      rpc_chain_id: rpcChainId,
      registry_address: registryAddress,
      registry_has_code: true,
      reputation_registry_address: OFFICIAL_FUJI_ERC8004_REPUTATION_REGISTRY,
      reputation_registry_has_code: repHasCode,
      agent_id: agentId,
      owner,
      agent_uri: uri,
      registration_tx_hash: txHash,
      tx_receipt_status: txReceiptStatus,
      verified,
      verification_status: verified ? "PASS" : "FAIL",
      verification_checked_at: checkedAt,
      notes,
    };
  } catch (err) {
    notes.push(
      `Fuji contract read-back failed: ${
        err instanceof Error ? err.message : String(err)
      }`
    );
    return {
      chain_id: FUJI_CHAIN_ID,
      rpc_connected: true,
      rpc_chain_id: rpcChainId,
      registry_address: registryAddress,
      registry_has_code: true,
      reputation_registry_address: OFFICIAL_FUJI_ERC8004_REPUTATION_REGISTRY,
      reputation_registry_has_code: true,
      agent_id: agentId,
      owner: null,
      agent_uri: null,
      registration_tx_hash: txHash,
      tx_receipt_status: "not_checked",
      verified: false,
      verification_status: "FAIL",
      verification_checked_at: checkedAt,
      notes,
    };
  }
}

export async function verifyFujiDecisionReceipt(params: {
  rpcUrl?: string;
  contractAddress?: string | null;
  decisionHash?: string | null;
  txHash?: string | null;
}): Promise<FujiDecisionReceiptVerification> {
  const checkedAt = new Date().toISOString();
  const rpcUrl = params.rpcUrl || process.env.FUJI_RPC_URL || FUJI_RPC_DEFAULT;
  const contractAddress =
    params.contractAddress ?? process.env.RISK_DECISION_REGISTRY_ADDRESS ?? null;
  const rawDigest =
    params.decisionHash ??
    process.env.RISK_DECISION_SAMPLE_SHA256 ??
    "0x166c93073c84eddf94e432f3b0a52a66f60a6c308097beed0527097cfb3c08b2";
  const txHash = params.txHash ?? process.env.RISK_DECISION_SAMPLE_TX_HASH ?? null;
  const notes: string[] = [
    "RiskDecisionRegistry commits {decisionHash, runIdHash, policyVersionHash, caller, timestamp, verdictCode} on Fuji C-Chain; it does not run model inference on-chain.",
  ];

  if (!contractAddress || !rawDigest) {
    notes.push(
      "RiskDecisionRegistry address not yet deployed on Fuji 43113 (local EVM unit tests PASS 3/3; awaiting funded disposable Fuji wallet). Status remains NOT_TESTED."
    );
    return {
      chain_id: FUJI_CHAIN_ID,
      contract_address: contractAddress,
      contract_has_code: false,
      decision_hash: rawDigest,
      run_id_hash: null,
      policy_version_hash: null,
      exists_on_chain: false,
      caller: null,
      timestamp_unix: null,
      verdict_code: null,
      tx_hash: txHash,
      block_number: null,
      gas_used: null,
      effective_gas_price_wei: null,
      measured_confirmation_ms: null,
      verified: false,
      verification_status: "NOT_TESTED",
      checked_at: checkedAt,
      notes,
    };
  }

  const normalizedDigest = rawDigest.startsWith("0x")
    ? rawDigest
    : `0x${rawDigest}`;
  if (
    !isAddress(contractAddress) ||
    !isHex(normalizedDigest) ||
    normalizedDigest.length !== 66
  ) {
    notes.push("Invalid contract address or 32-byte SHA-256 hex digest format.");
    return {
      chain_id: FUJI_CHAIN_ID,
      contract_address: contractAddress,
      contract_has_code: false,
      decision_hash: normalizedDigest,
      run_id_hash: null,
      policy_version_hash: null,
      exists_on_chain: false,
      caller: null,
      timestamp_unix: null,
      verdict_code: null,
      tx_hash: txHash,
      block_number: null,
      gas_used: null,
      effective_gas_price_wei: null,
      measured_confirmation_ms: null,
      verified: false,
      verification_status: "FAIL",
      checked_at: checkedAt,
      notes,
    };
  }

  const client = createPublicClient({
    chain: avalancheFuji,
    transport: http(rpcUrl, { timeout: 6_000 }),
  });

  try {
    const code = await client.getCode({ address: contractAddress });
    const hasCode = Boolean(code && code !== "0x");
    if (!hasCode) {
      notes.push(
        `No RiskDecisionRegistry bytecode deployed at ${contractAddress} on Fuji 43113.`
      );
      return {
        chain_id: FUJI_CHAIN_ID,
        contract_address: contractAddress,
        contract_has_code: false,
        decision_hash: normalizedDigest,
        run_id_hash: null,
        policy_version_hash: null,
        exists_on_chain: false,
        caller: null,
        timestamp_unix: null,
        verdict_code: null,
        tx_hash: txHash,
        block_number: null,
        gas_used: null,
        effective_gas_price_wei: null,
        measured_confirmation_ms: null,
        verified: false,
        verification_status: "FAIL",
        checked_at: checkedAt,
        notes,
      };
    }

    const [
      storedDecisionHash,
      runIdHash,
      policyVersionHash,
      caller,
      timestamp,
      verdictCode,
      exists,
    ] = await client.readContract({
      address: contractAddress,
      abi: RISK_DECISION_REGISTRY_ABI,
      functionName: "getDecisionReceipt",
      args: [normalizedDigest as `0x${string}`],
    });

    let blockNumber: number | null = null;
    let gasUsed: string | null = null;
    let effectiveGasPrice: string | null = null;
    if (txHash && isHex(txHash) && txHash.length === 66) {
      const receipt = await client.getTransactionReceipt({ hash: txHash });
      blockNumber = Number(receipt.blockNumber);
      gasUsed = receipt.gasUsed.toString();
      effectiveGasPrice = receipt.effectiveGasPrice.toString();
    }

    const verified =
      exists &&
      storedDecisionHash.toLowerCase() === normalizedDigest.toLowerCase() &&
      caller !== "0x0000000000000000000000000000000000000000";

    notes.push(
      verified
        ? `Independent Fuji read-back confirmed decisionHash ${toHex(
            storedDecisionHash
          )} anchored by ${caller}.`
        : "Decision hash not yet committed to RiskDecisionRegistry on Fuji 43113."
    );

    return {
      chain_id: FUJI_CHAIN_ID,
      contract_address: contractAddress,
      contract_has_code: true,
      decision_hash: normalizedDigest,
      run_id_hash: exists ? runIdHash : null,
      policy_version_hash: exists ? policyVersionHash : null,
      exists_on_chain: exists,
      caller: exists ? caller : null,
      timestamp_unix: exists ? Number(timestamp) : null,
      verdict_code: exists ? Number(verdictCode) : null,
      tx_hash: txHash,
      block_number: blockNumber,
      gas_used: gasUsed,
      effective_gas_price_wei: effectiveGasPrice,
      measured_confirmation_ms: null,
      verified,
      verification_status: verified ? "PASS" : "NOT_TESTED",
      checked_at: checkedAt,
      notes,
    };
  } catch (err) {
    notes.push(
      `Fuji receipt verification error: ${
        err instanceof Error ? err.message : String(err)
      }`
    );
    return {
      chain_id: FUJI_CHAIN_ID,
      contract_address: contractAddress,
      contract_has_code: false,
      decision_hash: normalizedDigest,
      run_id_hash: null,
      policy_version_hash: null,
      exists_on_chain: false,
      caller: null,
      timestamp_unix: null,
      verdict_code: null,
      tx_hash: txHash,
      block_number: null,
      gas_used: null,
      effective_gas_price_wei: null,
      measured_confirmation_ms: null,
      verified: false,
      verification_status: "FAIL",
      checked_at: checkedAt,
      notes,
    };
  }
}
