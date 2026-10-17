import { describe, expect, it } from "vitest";
import {
  connectFuji,
  deploymentTransaction,
  receiptTransaction,
  sendFujiTransaction,
  verifyFujiTransaction,
  EXPECTED_FUJI_ACCOUNT,
  type FujiPlan,
  type WalletProvider,
} from "../lib/fuji-wallet";

const hash = `0x${"11".repeat(32)}` as const;
const registry = "0x1111111111111111111111111111111111111111";
const plan: FujiPlan = {
  chain_id: 43113,
  expected_account: "0x3754131A55d043fC49eB93cEBfB381953cA41bB8",
  bytecode: "0x60006000",
  runtime_bytecode: "0x6001",
  decision_hash: `0x${"22".repeat(32)}`,
  run_id_hash: `0x${"33".repeat(32)}`,
  policy_version_hash: `0x${"44".repeat(32)}`,
  verdict_code: 2,
  evidence_source: "backend/evidence/amendment-http.json",
};

function storage() {
  const data = new Map<string, string>();
  return {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => { data.set(key, value); },
  };
}

function wallet(overrides: Record<string, unknown> = {}) {
  const calls: string[] = [];
  let chain = "0xa869";
  const provider: WalletProvider = {
    async request({ method }) {
      calls.push(method);
      if (method in overrides) {
        const value = overrides[method];
        if (value instanceof Error || (value && typeof value === "object" && "code" in value)) throw value;
        return value;
      }
      if (method === "eth_requestAccounts" || method === "eth_accounts") return [EXPECTED_FUJI_ACCOUNT];
      if (method === "eth_chainId") return chain;
      if (method === "wallet_switchEthereumChain") { chain = "0xa869"; return null; }
      if (method === "eth_estimateGas") return "0x80000";
      if (method === "eth_getBalance") return "0x3782dace9d90000";
      if (method === "eth_sendTransaction") return hash;
      throw new Error("Unexpected method: " + method);
    },
  };
  return { provider, calls };
}

describe("MetaMask Fuji signing boundary", () => {
  it("explains missing extension without sending anything", async () => {
    await expect(connectFuji(undefined)).rejects.toThrow(/MetaMask/);
  });
  it("connection grants account access only, never sends a transaction", async () => {
    const { provider, calls } = wallet();
    expect((await connectFuji(provider)).account).toBe(EXPECTED_FUJI_ACCOUNT);
    expect(calls).not.toContain("eth_sendTransaction");
  });
  it("switches from mainnet to Fuji without sending a transaction", async () => {
    const { provider, calls } = wallet();
    let first = true;
    const original = provider.request;
    provider.request = async (args) => {
      if (args.method === "eth_chainId" && first) { first = false; return "0x1"; }
      return original(args);
    };
    await connectFuji(provider);
    expect(calls).toContain("wallet_switchEthereumChain");
    expect(calls).not.toContain("eth_sendTransaction");
  });
  it("refuses a different account", async () => {
    const { provider, calls } = wallet({ eth_requestAccounts: [registry] });
    await expect(connectFuji(provider)).rejects.toThrow(/account/i);
    expect(calls).not.toContain("eth_sendTransaction");
  });
  it("blocks a network change before submission", async () => {
    const { provider, calls } = wallet({ eth_chainId: "0xa86a" });
    await expect(sendFujiTransaction(provider, deploymentTransaction(plan), storage())).rejects.toThrow(/Fuji/);
    expect(calls).not.toContain("eth_sendTransaction");
  });
  it("sends zero value with fixed chain, bounded fees and no automatic second send", async () => {
    const { provider, calls } = wallet();
    const tx = deploymentTransaction(plan);
    expect(tx.value).toBe("0x0");
    expect(tx.chainId).toBe("0xa869");
    const saved = storage();
    expect((await sendFujiTransaction(provider, tx, saved)).hash).toBe(hash);
    await expect(sendFujiTransaction(provider, tx, saved)).rejects.toThrow(/already|existing/i);
    expect(calls.filter(x => x === "eth_sendTransaction")).toHaveLength(1);
  });
  it("persists unknown submission and refuses a retry after ambiguous timeout", async () => {
    const { provider, calls } = wallet({ eth_sendTransaction: new Error("timeout") });
    const saved = storage();
    const tx = deploymentTransaction(plan);
    await expect(sendFujiTransaction(provider, tx, saved)).rejects.toThrow(/unknown/i);
    await expect(sendFujiTransaction(provider, tx, saved)).rejects.toThrow(/already|existing/i);
    expect(calls.filter(x => x === "eth_sendTransaction")).toHaveLength(1);
  });
  it("a deliberate user rejection permits a later deliberate attempt", async () => {
    const { provider, calls } = wallet({ eth_sendTransaction: { code: 4001 } });
    const saved = storage();
    for (let i = 0; i < 2; i++) await expect(sendFujiTransaction(provider, deploymentTransaction(plan), saved)).rejects.toThrow(/reject/i);
    expect(calls.filter(x => x === "eth_sendTransaction")).toHaveLength(2);
  });
  it("blocks excess gas before opening the signing prompt", async () => {
    const { provider, calls } = wallet({ eth_estimateGas: "0xffffff" });
    await expect(sendFujiTransaction(provider, deploymentTransaction(plan), storage())).rejects.toThrow(/gas/i);
    expect(calls).not.toContain("eth_sendTransaction");
  });
  it("uses only the recorded HALT digest in receipt calldata", () => {
    const tx = receiptTransaction(plan, registry);
    expect(tx.to).toBe(registry);
    expect(tx.data).toContain(plan.decision_hash.slice(2));
    expect(tx.value).toBe("0x0");
    expect(() => receiptTransaction({ ...plan, verdict_code: 0 }, registry)).toThrow();
  });
});

describe("Independent Fuji confirmation", () => {
  function reader() {
    return {
      getChainId: async () => 43113,
      getTransactionReceipt: async () => ({ status: "success", contractAddress: registry, blockNumber: BigInt(12), gasUsed: BigInt(100), effectiveGasPrice: BigInt(2) }),
      getTransaction: async () => ({ from: EXPECTED_FUJI_ACCOUNT, to: null, input: plan.bytecode, value: BigInt(0) }),
      getCode: async () => plan.runtime_bytecode,
      readContract: async () => EXPECTED_FUJI_ACCOUNT,
    };
  }
  it("verifies successful deployment, bytecode, sender and owner", async () => {
    const proof = await verifyFujiTransaction(reader(), plan, "deploy", hash);
    expect(proof.verified).toBe(true);
    expect(proof.contract_address).toBe(registry);
    expect(proof.fee_wei).toBe("200");
  });
  it("never treats a reverted transaction as a successful deployment", async () => {
    const rpc = reader();
    rpc.getTransactionReceipt = async () => ({ status: "reverted", contractAddress: registry, blockNumber: BigInt(12), gasUsed: BigInt(100), effectiveGasPrice: BigInt(2) });
    await expect(verifyFujiTransaction(rpc, plan, "deploy", hash)).rejects.toThrow(/revert/i);
  });
  it("rejects mismatched deployed runtime bytecode", async () => {
    const rpc = reader();
    rpc.getCode = async () => "0x6002";
    await expect(verifyFujiTransaction(rpc, plan, "deploy", hash)).rejects.toThrow(/bytecode/i);
  });
  it("rejects independent RPC on another chain", async () => {
    const rpc = reader(); rpc.getChainId = async () => 43114;
    await expect(verifyFujiTransaction(rpc, plan, "deploy", hash)).rejects.toThrow(/Fuji/);
  });
  it("checks every recorded receipt field against the reviewed assessment", async () => {
    const expected = receiptTransaction(plan, registry);
    const rpc = {
      ...reader(),
      getTransaction: async () => ({ from: EXPECTED_FUJI_ACCOUNT, to: registry, input: expected.data, value: BigInt(0) }),
      readContract: async () => [plan.decision_hash, plan.run_id_hash, plan.policy_version_hash, EXPECTED_FUJI_ACCOUNT, BigInt(1792231900), 2, true],
    };
    expect((await verifyFujiTransaction(rpc, plan, "record", hash, registry)).verified).toBe(true);
    rpc.readContract = async () => [plan.decision_hash, plan.run_id_hash, plan.policy_version_hash, EXPECTED_FUJI_ACCOUNT, BigInt(1792231900), 1, true];
    await expect(verifyFujiTransaction(rpc, plan, "record", hash, registry)).rejects.toThrow(/receipt.*match/i);
  });
});
