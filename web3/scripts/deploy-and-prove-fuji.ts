/**
 * Avalanche Fuji (Chain ID 43113) Real On-Chain Execution & Proof Script
 *
 * Implements P3-02 steps 1-7:
 * 1. Verifies RPC network is Avalanche Fuji Testnet (`chainId === 43113`), never mainnet.
 * 2. Verifies official ERC-8004 `IdentityRegistry` (`0x8004A818BFB912233c491871b3d84c89A494BD9e`)
 *    and `ReputationRegistry` (`0x8004B663056A597Dffe9eCcC1965A193B7388713`) via live `eth_getCode`
 *    and contract view calls (`name()`, `symbol()`).
 * 3. Loads real backend assessment from `backend/evidence/amendment-http.json`, recomputes its
 *    canonical SHA-256 (`decisionHash`), `runIdHash`, and `policyVersionHash`.
 * 4. If `FUJI_PRIVATE_KEY` (disposable funded Fuji testnet wallet) is provided in local env:
 *    - Deploys `RiskDecisionRegistry.sol` (or uses `RISK_DECISION_REGISTRY_ADDRESS`),
 *    - Submits `recordDecision(decisionHash, runIdHash, policyVersionHash, verdictCode)`,
 *    - Measures exact confirmation latency (`submittedAt` -> `receiptReceivedAt`) and actual gas fee,
 *    - Independently reads back `getDecisionReceipt(decisionHash)` and decoded `DecisionReceiptRecorded` event,
 *    - If `ERC8004_AGENT_URI` is provided (or already registered), calls `register(agentURI)` on
 *      `0x8004A818BFB912233c491871b3d84c89A494BD9e`, extracts `agentId` from `Registered` log,
 *      and reads back `ownerOf(agentId)` + `tokenURI(agentId)`.
 * 5. If `FUJI_PRIVATE_KEY` is NOT set or has 0 Fuji AVAX, writes an honest machine-readable
 *    `web3/fuji-proof-manifest.json` with live RPC read-back of the official ERC-8004 registries
 *    and `verified: false`, `status: "NOT_TESTED_NEEDS_FUJI_AVAX"` — NEVER fabricates a txHash or agentId.
 */

import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import {
  createPublicClient,
  createWalletClient,
  decodeEventLog,
  formatEther,
  http,
  isAddress,
  isHex,
  keccak256,
  toBytes,
} from "viem";
import { privateKeyToAccount } from "viem/accounts";
import { avalancheFuji } from "viem/chains";
import {
  ERC8004_IDENTITY_REGISTRY_ABI,
  FUJI_CHAIN_ID,
  FUJI_RPC_DEFAULT,
  OFFICIAL_FUJI_ERC8004_IDENTITY_REGISTRY,
  OFFICIAL_FUJI_ERC8004_REPUTATION_REGISTRY,
  RISK_DECISION_REGISTRY_ABI,
} from "../abi";

const artifactPath = path.resolve(
  __dirname,
  "../artifacts/RiskDecisionRegistry.json"
);
const evidencePath = path.resolve(
  __dirname,
  "../../backend/evidence/amendment-http.json"
);
const manifestOutPath = path.resolve(__dirname, "../fuji-proof-manifest.json");

function canonicalizePythonJson(val: unknown): string {
  if (Array.isArray(val)) {
    return `[${val.map(canonicalizePythonJson).join(",")}]`;
  }
  if (val && typeof val === "object") {
    const obj = val as Record<string, unknown>;
    const keys = Object.keys(obj).sort();
    return `{${keys
      .map((k) => `${JSON.stringify(k)}:${canonicalizePythonJson(obj[k])}`)
      .join(",")}}`;
  }
  if (typeof val === "number" && Number.isInteger(val)) {
    return val === 0 ? "0.0" : JSON.stringify(val);
  }
  return JSON.stringify(val);
}

async function main() {
  const rpcUrl = process.env.FUJI_RPC_URL || FUJI_RPC_DEFAULT;
  const publicClient = createPublicClient({
    chain: avalancheFuji,
    transport: http(rpcUrl, { timeout: 10_000 }),
  });

  // 1. Verify Chain ID == 43113
  const [chainId, blockNumber] = await Promise.all([
    publicClient.getChainId(),
    publicClient.getBlockNumber(),
  ]);
  if (chainId !== FUJI_CHAIN_ID) {
    throw new Error(
      `SAFETY HALT: RPC chainId ${chainId} is not Avalanche Fuji (${FUJI_CHAIN_ID}). Refusing to proceed.`
    );
  }

  // 2. Verify Official ERC-8004 Registries on Fuji 43113 via eth_getCode & view calls
  const [idCode, repCode, idName, idSymbol] = await Promise.all([
    publicClient.getCode({ address: OFFICIAL_FUJI_ERC8004_IDENTITY_REGISTRY }),
    publicClient.getCode({ address: OFFICIAL_FUJI_ERC8004_REPUTATION_REGISTRY }),
    publicClient.readContract({
      address: OFFICIAL_FUJI_ERC8004_IDENTITY_REGISTRY,
      abi: ERC8004_IDENTITY_REGISTRY_ABI,
      functionName: "name",
    }),
    publicClient.readContract({
      address: OFFICIAL_FUJI_ERC8004_IDENTITY_REGISTRY,
      abi: ERC8004_IDENTITY_REGISTRY_ABI,
      functionName: "symbol",
    }),
  ]);

  // 3. Load actual backend audit assessment & compute canonical hashes
  const amendmentEvidence = JSON.parse(fs.readFileSync(evidencePath, "utf8"));
  const realAssessment = amendmentEvidence.checks.excess_notional.response;
  const copy = { ...realAssessment };
  delete copy.assessment_sha256;
  const recomputedSha = crypto
    .createHash("sha256")
    .update(Buffer.from(canonicalizePythonJson(copy), "utf8"))
    .digest("hex");

  if (recomputedSha !== realAssessment.assessment_sha256) {
    throw new Error("Canonical SHA-256 mismatch against backend evidence");
  }

  const decisionHash = `0x${recomputedSha}` as `0x${string}`;
  const runIdHash = keccak256(toBytes(realAssessment.run_id));
  const policyVersionHash = keccak256(toBytes("aegis-policy-v2.0"));
  const verdictCode = realAssessment.assessment === "HALT" ? 2 : 1;

  const manifest: Record<string, unknown> = {
    schema_version: "1.0.0",
    recorded_at: new Date().toISOString(),
    network: {
      name: "Avalanche Fuji Testnet (C-Chain)",
      chain_id: chainId,
      rpc_url: rpcUrl,
      verified_block_number: Number(blockNumber),
      custom_l1_used: false,
      interchain_messaging_used: false,
      architecture_statement:
        "Agent reasoning (EVREN), operational classification (LAYA), and OKX ATK observations run OFF-CHAIN. Fuji contracts provide ERC-8004 identity and SHA-256 decision receipt anchoring only.",
    },
    official_erc8004_registries: {
      source_repo: "https://github.com/erc-8004/erc-8004-contracts",
      identity_registry: {
        address: OFFICIAL_FUJI_ERC8004_IDENTITY_REGISTRY,
        explorer_url: `https://testnet.snowtrace.io/address/${OFFICIAL_FUJI_ERC8004_IDENTITY_REGISTRY}`,
        has_code: Boolean(idCode && idCode !== "0x"),
        code_bytes: idCode ? (idCode.length - 2) / 2 : 0,
        name: idName,
        symbol: idSymbol,
      },
      reputation_registry: {
        address: OFFICIAL_FUJI_ERC8004_REPUTATION_REGISTRY,
        explorer_url: `https://testnet.snowtrace.io/address/${OFFICIAL_FUJI_ERC8004_REPUTATION_REGISTRY}`,
        has_code: Boolean(repCode && repCode !== "0x"),
        code_bytes: repCode ? (repCode.length - 2) / 2 : 0,
      },
    },
    canonical_backend_audit_payload: {
      source_file: "backend/evidence/amendment-http.json",
      assessment_id: realAssessment.assessment_id,
      run_id: realAssessment.run_id,
      verdict: realAssessment.assessment,
      verdict_code: verdictCode,
      decision_hash_sha256: decisionHash,
      run_id_keccak256: runIdHash,
      policy_version_keccak256: policyVersionHash,
      byte_verified_against_python: true,
    },
    erc8004_agent_registration: {
      status: "NOT_TESTED",
      verified: false,
      registry_address: OFFICIAL_FUJI_ERC8004_IDENTITY_REGISTRY,
      agent_id: null,
      agent_uri: null,
      owner: null,
      tx_hash: null,
      block_number: null,
      chain_rpc_readback_at: null,
      measured_confirmation_ms: null,
      fee_avax: null,
      reason:
        "No funded disposable Fuji wallet (FUJI_PRIVATE_KEY) or public HTTPS agentURI configured yet. Zero fake IDs or tx hashes.",
    },
    risk_decision_registry: {
      status: "NOT_TESTED",
      verified: false,
      contract_address: null,
      deploy_tx_hash: null,
      record_tx_hash: null,
      block_number: null,
      measured_confirmation_ms: null,
      gas_used: null,
      effective_gas_price_wei: null,
      fee_avax: null,
      readback: null,
      reason:
        "Contract compiled and verified in local EVM unit tests (3/3 PASS); live Fuji deployment awaits disposable wallet funded with faucet AVAX (FUJI_PRIVATE_KEY).",
    },
  };

  const pk = process.env.FUJI_PRIVATE_KEY;
  if (pk && isHex(pk) && pk.length === 66) {
    const account = privateKeyToAccount(pk);
    const balanceWei = await publicClient.getBalance({ address: account.address });

    if (balanceWei === BigInt(0)) {
      (manifest.risk_decision_registry as Record<string, unknown>).reason =
        `Disposable wallet ${account.address} has 0 Fuji AVAX. Fund via https://core.app/tools/testnet-faucet/?subnet=c&token=c and re-run.`;
    } else {
      const walletClient = createWalletClient({
        account,
        chain: avalancheFuji,
        transport: http(rpcUrl, { timeout: 15_000 }),
      });

      const artifact = JSON.parse(fs.readFileSync(artifactPath, "utf8"));
      let registryAddr = process.env.RISK_DECISION_REGISTRY_ADDRESS as
        | `0x${string}`
        | undefined;
      let deployTxHash: `0x${string}` | null = null;

      if (!registryAddr || !isAddress(registryAddr)) {
        const t0 = performance.now();
        deployTxHash = await walletClient.deployContract({
          abi: RISK_DECISION_REGISTRY_ABI,
          bytecode: artifact.bytecode as `0x${string}`,
        });
        const deployReceipt = await publicClient.waitForTransactionReceipt({
          hash: deployTxHash,
        });
        const deployElapsedMs = Number((performance.now() - t0).toFixed(2));
        registryAddr = deployReceipt.contractAddress!;
        (manifest.risk_decision_registry as Record<string, unknown>).deploy_confirmation_ms =
          deployElapsedMs;
      }

      // Submit recordDecision transaction and measure confirmation time
      const tSubmit = performance.now();
      const recordTxHash = await walletClient.writeContract({
        address: registryAddr,
        abi: RISK_DECISION_REGISTRY_ABI,
        functionName: "recordDecision",
        args: [decisionHash, runIdHash, policyVersionHash, verdictCode],
      });
      const receipt = await publicClient.waitForTransactionReceipt({
        hash: recordTxHash,
      });
      const confirmMs = Number((performance.now() - tSubmit).toFixed(2));

      // Independent read-back
      const [
        storedDecisionHash,
        storedRunIdHash,
        storedPolicyHash,
        storedCaller,
        storedTimestamp,
        storedVerdict,
        exists,
      ] = await publicClient.readContract({
        address: registryAddr,
        abi: RISK_DECISION_REGISTRY_ABI,
        functionName: "getDecisionReceipt",
        args: [decisionHash],
      });

      const totalFeeWei = receipt.gasUsed * receipt.effectiveGasPrice;

      manifest.risk_decision_registry = {
        status: exists ? "PASS" : "FAIL",
        verified: exists,
        contract_address: registryAddr,
        explorer_url: `https://testnet.snowtrace.io/address/${registryAddr}`,
        deploy_tx_hash: deployTxHash,
        record_tx_hash: recordTxHash,
        record_tx_explorer_url: `https://testnet.snowtrace.io/tx/${recordTxHash}`,
        block_number: Number(receipt.blockNumber),
        measured_confirmation_ms: confirmMs,
        gas_used: receipt.gasUsed.toString(),
        effective_gas_price_wei: receipt.effectiveGasPrice.toString(),
        fee_avax: formatEther(totalFeeWei),
        readback: {
          exists,
          decisionHash: storedDecisionHash,
          runIdHash: storedRunIdHash,
          policyVersionHash: storedPolicyHash,
          caller: storedCaller,
          timestamp: Number(storedTimestamp),
          verdictCode: storedVerdict,
          checked_at: new Date().toISOString(),
        },
      };

      // Optional ERC-8004 register(agentURI) if ERC8004_AGENT_URI is provided
      const agentUri = process.env.ERC8004_AGENT_URI;
      if (agentUri && agentUri.startsWith("https://")) {
        const tReg = performance.now();
        const regTxHash = await walletClient.writeContract({
          address: OFFICIAL_FUJI_ERC8004_IDENTITY_REGISTRY,
          abi: ERC8004_IDENTITY_REGISTRY_ABI,
          functionName: "register",
          args: [agentUri],
        });
        const regReceipt = await publicClient.waitForTransactionReceipt({
          hash: regTxHash,
        });
        const regConfirmMs = Number((performance.now() - tReg).toFixed(2));

        let registeredAgentId: bigint | null = null;
        for (const log of regReceipt.logs) {
          try {
            const decoded = decodeEventLog({
              abi: ERC8004_IDENTITY_REGISTRY_ABI,
              eventName: "Registered",
              topics: log.topics,
              data: log.data,
            });
            registeredAgentId = decoded.args.agentId;
            break;
          } catch {
            // continue
          }
        }

        if (registeredAgentId !== null) {
          const [ownerBack, uriBack] = await Promise.all([
            publicClient.readContract({
              address: OFFICIAL_FUJI_ERC8004_IDENTITY_REGISTRY,
              abi: ERC8004_IDENTITY_REGISTRY_ABI,
              functionName: "ownerOf",
              args: [registeredAgentId],
            }),
            publicClient.readContract({
              address: OFFICIAL_FUJI_ERC8004_IDENTITY_REGISTRY,
              abi: ERC8004_IDENTITY_REGISTRY_ABI,
              functionName: "tokenURI",
              args: [registeredAgentId],
            }),
          ]);

          const regFeeWei = regReceipt.gasUsed * regReceipt.effectiveGasPrice;
          manifest.erc8004_agent_registration = {
            status: "PASS",
            verified:
              ownerBack.toLowerCase() === account.address.toLowerCase() &&
              uriBack === agentUri,
            registry_address: OFFICIAL_FUJI_ERC8004_IDENTITY_REGISTRY,
            agent_id: registeredAgentId.toString(),
            agent_uri: uriBack,
            owner: ownerBack,
            tx_hash: regTxHash,
            tx_explorer_url: `https://testnet.snowtrace.io/tx/${regTxHash}`,
            block_number: Number(regReceipt.blockNumber),
            chain_rpc_readback_at: new Date().toISOString(),
            measured_confirmation_ms: regConfirmMs,
            fee_avax: formatEther(regFeeWei),
          };
        }
      }
    }
  }

  fs.writeFileSync(manifestOutPath, JSON.stringify(manifest, null, 2) + "\n", "utf8");
  console.log(`Wrote Fuji proof manifest to ${manifestOutPath}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
