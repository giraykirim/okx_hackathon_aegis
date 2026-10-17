import { encodeFunctionData, isAddress, keccak256, parseAbi, toBytes, type Address, type Hex } from "viem";

export const EXPECTED_FUJI_ACCOUNT = "0x3754131A55d043fC49eB93cEBfB381953cA41bB8" as const;
export const FUJI_RPC = "https://api.avax-test.network/ext/bc/C/rpc";
export const RECEIPT_ABI = parseAbi([
  "function owner() view returns (address)",
  "function recordDecision(bytes32 decisionHash, bytes32 runIdHash, bytes32 policyVersionHash, uint8 verdictCode)",
  "function getDecisionReceipt(bytes32 decisionHash) view returns (bytes32, bytes32, bytes32, address, uint64, uint8, bool)",
]);

export interface WalletProvider {
  request(args: { method: string; params?: unknown[] }): Promise<unknown>;
  on?(event: string, listener: () => void): void;
  removeListener?(event: string, listener: () => void): void;
}
export interface FujiPlan {
  chain_id: 43113;
  expected_account: Address;
  bytecode: Hex;
  runtime_bytecode: Hex;
  decision_hash: Hex;
  run_id_hash: Hex;
  policy_version_hash: Hex;
  verdict_code: number;
  evidence_source: string;
}
export interface FujiTransaction {
  from: Address;
  to?: Address;
  data: Hex;
  value: "0x0";
  chainId: "0xa869";
  gas: Hex;
  maxFeePerGas: Hex;
  maxPriorityFeePerGas: Hex;
}
export type Operation = { status: "AWAITING_WALLET" | "SUBMITTED" | "UNKNOWN" | "REJECTED"; hash?: Hex; requested_at: string; submitted_at?: string };
type JournalStorage = Pick<Storage, "getItem" | "setItem">;
const same = (a: string, b: string) => a.toLowerCase() === b.toLowerCase();
const validHex = (value: unknown): value is Hex => typeof value === "string" && /^0x(?:[a-fA-F0-9]{2})+$/.test(value);
const isHash = (value: unknown): value is Hex => validHex(value) && value.length === 66;
const errorCode = (error: unknown) => error && typeof error === "object" && "code" in error ? error.code : undefined;

async function assertWallet(provider: WalletProvider, requestAccess = false) {
  const accounts = await provider.request({ method: requestAccess ? "eth_requestAccounts" : "eth_accounts" });
  if (!Array.isArray(accounts) || !isAddress(accounts[0] ?? "") || !same(accounts[0], EXPECTED_FUJI_ACCOUNT)) {
    throw new Error(`Select the funded test account ${EXPECTED_FUJI_ACCOUNT} in MetaMask.`);
  }
  return accounts[0] as Address;
}
async function assertFuji(provider: WalletProvider) {
  if (await provider.request({ method: "eth_chainId" }) !== "0xa869") throw new Error("Select Avalanche Fuji (43113); submission blocked.");
}

export async function connectFuji(provider: WalletProvider | undefined) {
  if (!provider) throw new Error("MetaMask is unavailable here. Open this page in the browser where the MetaMask extension is installed.");
  await assertWallet(provider, true);
  if (await provider.request({ method: "eth_chainId" }) !== "0xa869") {
    try {
      await provider.request({ method: "wallet_switchEthereumChain", params: [{ chainId: "0xa869" }] });
    } catch (error) {
      if (errorCode(error) !== 4902) throw new Error("Fuji network switch was not approved. No transaction sent.");
      await provider.request({ method: "wallet_addEthereumChain", params: [{ chainId: "0xa869", chainName: "Avalanche Fuji C-Chain", nativeCurrency: { name: "Test AVAX", symbol: "AVAX", decimals: 18 }, rpcUrls: [FUJI_RPC], blockExplorerUrls: ["https://testnet.snowtrace.io"] }] });
      await provider.request({ method: "wallet_switchEthereumChain", params: [{ chainId: "0xa869" }] });
    }
  }
  await assertFuji(provider);
  return { account: await assertWallet(provider), chainId: 43113 as const };
}

function validatePlan(plan: FujiPlan) {
  if (plan.chain_id !== 43113 || !same(plan.expected_account, EXPECTED_FUJI_ACCOUNT) || !validHex(plan.bytecode) || !validHex(plan.runtime_bytecode)
    || ![plan.decision_hash, plan.run_id_hash, plan.policy_version_hash].every(isHash) || ![1, 2, 3].includes(plan.verdict_code)) throw new Error("Invalid Fuji transaction plan.");
}
export function deploymentTransaction(plan: FujiPlan): FujiTransaction {
  validatePlan(plan);
  return { from: EXPECTED_FUJI_ACCOUNT, data: plan.bytecode, value: "0x0", chainId: "0xa869", gas: "0xf4240", maxFeePerGas: "0x5d21dba00", maxPriorityFeePerGas: "0x3b9aca00" };
}
export function receiptTransaction(plan: FujiPlan, registry: string): FujiTransaction {
  validatePlan(plan);
  if (!isAddress(registry)) throw new Error("Invalid verified receipt contract address.");
  return { ...deploymentTransaction(plan), to: registry, gas: "0x3d090", data: encodeFunctionData({ abi: RECEIPT_ABI, functionName: "recordDecision", args: [plan.decision_hash, plan.run_id_hash, plan.policy_version_hash, plan.verdict_code] }) };
}

export function operationKey(tx: FujiTransaction) {
  return "aegis:fuji:operation:" + keccak256(toBytes(JSON.stringify(tx)));
}
export function loadOperation(storage: JournalStorage, tx: FujiTransaction): Operation | null {
  const saved = storage.getItem(operationKey(tx));
  if (!saved) return null;
  const state = JSON.parse(saved);
  if (!state || !["AWAITING_WALLET", "SUBMITTED", "UNKNOWN", "REJECTED"].includes(state.status) || (state.hash && !isHash(state.hash))) throw new Error("Corrupt local transaction journal; submission blocked.");
  return state;
}

export async function sendFujiTransaction(provider: WalletProvider, tx: FujiTransaction, storage: JournalStorage): Promise<Operation> {
  if (tx.chainId !== "0xa869" || tx.value !== "0x0" || !same(tx.from, EXPECTED_FUJI_ACCOUNT) || !validHex(tx.data)
    || BigInt(tx.gas) > BigInt(1_000_000) || BigInt(tx.maxFeePerGas) > BigInt(25_000_000_000) || BigInt(tx.maxPriorityFeePerGas) > BigInt(1_000_000_000)) throw new Error("Unsafe Fuji transaction refused.");
  const assertUnused = () => {
    const previous = loadOperation(storage, tx);
    if (previous && previous.status !== "REJECTED") throw new Error("An existing transaction attempt is already recorded. Recheck it; do not resubmit.");
  };
  assertUnused();
  await assertWallet(provider); await assertFuji(provider);
  const estimate = await provider.request({ method: "eth_estimateGas", params: [tx] });
  if (typeof estimate !== "string" || !/^0x[\da-f]+$/i.test(estimate) || BigInt(estimate) > BigInt(tx.gas)) throw new Error("Estimated gas exceeds the fixed test budget.");
  const balance = await provider.request({ method: "eth_getBalance", params: [tx.from, "latest"] });
  if (typeof balance !== "string" || !/^0x[\da-f]+$/i.test(balance) || BigInt(balance) < BigInt(tx.gas) * BigInt(tx.maxFeePerGas)) throw new Error("Insufficient test AVAX for the maximum fee budget.");
  await assertWallet(provider); await assertFuji(provider);
  assertUnused();
  const pending: Operation = { status: "AWAITING_WALLET", requested_at: new Date().toISOString() };
  storage.setItem(operationKey(tx), JSON.stringify(pending));
  try {
    const hash = await provider.request({ method: "eth_sendTransaction", params: [tx] });
    if (!isHash(hash)) throw new Error("Unknown transaction response");
    const submitted: Operation = { ...pending, status: "SUBMITTED", hash, submitted_at: new Date().toISOString() };
    storage.setItem(operationKey(tx), JSON.stringify(submitted));
    return submitted;
  } catch (error) {
    const rejected = errorCode(error) === 4001;
    storage.setItem(operationKey(tx), JSON.stringify({ ...pending, status: rejected ? "REJECTED" : "UNKNOWN" }));
    throw new Error(rejected ? "Transaction rejected in MetaMask; no retry was sent." : "Submission status is unknown. Check MetaMask activity before taking any further action. No automatic retry.");
  }
}

interface FujiReader {
  getChainId(): Promise<number>;
  getTransactionReceipt(args: { hash: Hex }): Promise<{ status: string; contractAddress?: string | null; blockNumber: bigint; gasUsed: bigint; effectiveGasPrice: bigint }>;
  getTransaction(args: { hash: Hex }): Promise<{ from: string; to: string | null; input: string; value: bigint }>;
  getCode(args: { address: Address }): Promise<string | undefined>;
  readContract(args: { address: Address; abi: typeof RECEIPT_ABI; functionName: "owner" | "getDecisionReceipt"; args?: readonly [Hex] }): Promise<unknown>;
}
export interface FujiProof {
  verified: true;
  chain_id: 43113;
  kind: "deploy" | "record";
  transaction_hash: Hex;
  contract_address: Address;
  decision_hash: Hex;
  block_number: string;
  gas_used: string;
  fee_wei: string;
  checked_at: string;
}
export async function verifyFujiTransaction(client: FujiReader, plan: FujiPlan, kind: "deploy" | "record", hash: Hex, registry?: Address): Promise<FujiProof> {
  validatePlan(plan);
  if (!isHash(hash) || await client.getChainId() !== 43113) throw new Error("Independent RPC must be on Fuji (43113).");
  const receipt = await client.getTransactionReceipt({ hash });
  if (receipt.status !== "success") throw new Error("Transaction reverted; it is not a successful deployment or receipt.");
  const address = kind === "deploy" ? receipt.contractAddress : registry;
  if (!address || !isAddress(address)) throw new Error("Confirmed contract address unavailable.");
  const tx = await client.getTransaction({ hash });
  const expected = kind === "deploy" ? deploymentTransaction(plan) : receiptTransaction(plan, address);
  if (!same(tx.from, EXPECTED_FUJI_ACCOUNT) || tx.value !== BigInt(0) || !same(tx.input, expected.data) || (kind === "deploy" ? tx.to !== null : !tx.to || !same(tx.to, address))) throw new Error("Confirmed transaction does not match the reviewed plan.");
  const code = await client.getCode({ address });
  if (!code || !same(code, plan.runtime_bytecode)) throw new Error("Deployed bytecode does not match the compiled registry.");
  if (kind === "deploy") {
    const owner = await client.readContract({ address, abi: RECEIPT_ABI, functionName: "owner" });
    if (typeof owner !== "string" || !same(owner, EXPECTED_FUJI_ACCOUNT)) throw new Error("Deployed registry owner mismatch.");
  } else {
    const stored = await client.readContract({ address, abi: RECEIPT_ABI, functionName: "getDecisionReceipt", args: [plan.decision_hash] });
    if (!Array.isArray(stored) || stored.length !== 7 || stored[6] !== true || !same(String(stored[0]), plan.decision_hash) || !same(String(stored[1]), plan.run_id_hash) || !same(String(stored[2]), plan.policy_version_hash) || !same(String(stored[3]), EXPECTED_FUJI_ACCOUNT) || BigInt(stored[4]) <= BigInt(0) || Number(stored[5]) !== plan.verdict_code) throw new Error("On-chain receipt does not match the recorded backend assessment.");
  }
  return { verified: true, chain_id: 43113, kind, transaction_hash: hash, contract_address: address, decision_hash: plan.decision_hash, block_number: receipt.blockNumber.toString(), gas_used: receipt.gasUsed.toString(), fee_wei: (receipt.gasUsed * receipt.effectiveGasPrice).toString(), checked_at: new Date().toISOString() };
}
