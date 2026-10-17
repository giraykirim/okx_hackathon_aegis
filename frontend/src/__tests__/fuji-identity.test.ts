import { describe, expect, it } from "vitest";
import { encodeAbiParameters, encodeEventTopics, type Hex } from "viem";
import { EXPECTED_FUJI_ACCOUNT } from "../lib/fuji-wallet";
import { AGENT_METADATA_URI, IDENTITY_ABI, IDENTITY_REGISTRY, registrationTransaction, verifyRegistration, assertUnregistered } from "../lib/fuji-identity";

const hash = `0x${"aa".repeat(32)}` as Hex;
const id = BigInt(987); // UNIT ONLY. Never displayed as a real agent ID.
const topics = encodeEventTopics({ abi: IDENTITY_ABI, eventName: "Registered", args: { agentId: id, owner: EXPECTED_FUJI_ACCOUNT } });
const log: { address: string; topics: Hex[]; data: Hex } = { address: IDENTITY_REGISTRY, topics: topics as Hex[], data: encodeAbiParameters([{ type: "string" }], [AGENT_METADATA_URI]) };
function reader() {
  return {
    getChainId: async () => 43113,
    getCode: async () => "0x6001",
    getTransactionReceipt: async () => ({ status: "success", blockNumber: BigInt(12), gasUsed: BigInt(200), effectiveGasPrice: BigInt(3), logs: [log] }),
    getTransaction: async () => ({ from: EXPECTED_FUJI_ACCOUNT, to: IDENTITY_REGISTRY, value: BigInt(0), input: registrationTransaction().data }),
    readContract: async (args: { functionName: string }): Promise<unknown> => args.functionName === "ownerOf" ? EXPECTED_FUJI_ACCOUNT : args.functionName === "tokenURI" ? AGENT_METADATA_URI : BigInt(0),
  };
}

describe("Fuji ERC-8004 identity registration", () => {
  it("prepares exactly register(public metadata URI) on the official Fuji registry with zero transfer", () => {
    const tx = registrationTransaction();
    expect(tx.to).toBe(IDENTITY_REGISTRY); expect(tx.from).toBe(EXPECTED_FUJI_ACCOUNT);
    expect(tx.value).toBe("0x0"); expect(tx.chainId).toBe("0xa869");
    expect(BigInt(tx.gas) * BigInt(tx.maxFeePerGas)).toBeLessThanOrEqual(BigInt("12500000000000000"));
  });
  it("blocks minting when the wallet already owns an identity", async () => {
    const rpc = reader(); rpc.readContract = async () => BigInt(1);
    await expect(assertUnregistered(rpc)).rejects.toThrow(/existing|already/i);
  });
  it("requires Fuji and live registry code before minting", async () => {
    const rpc = reader(); rpc.getChainId = async () => 43114;
    await expect(assertUnregistered(rpc)).rejects.toThrow(/Fuji/);
  });
  it("extracts the ID from the actual event and verifies owner and tokenURI", async () => {
    const proof = await verifyRegistration(reader(), hash);
    expect(proof.agentId).toBe(id.toString()); expect(proof.owner).toBe(EXPECTED_FUJI_ACCOUNT);
    expect(proof.agentURI).toBe(AGENT_METADATA_URI); expect(proof.verified).toBe(true);
    expect(proof.fee_wei).toBe("600");
  });
  it("rejects reverted receipts", async () => {
    const rpc = reader(); const receipt = await rpc.getTransactionReceipt();
    rpc.getTransactionReceipt = async () => ({ ...receipt, status: "reverted" });
    await expect(verifyRegistration(rpc, hash)).rejects.toThrow(/revert/i);
  });
  it("does not accept a Registered event emitted by another contract", async () => {
    const rpc = reader(); const receipt = await rpc.getTransactionReceipt();
    rpc.getTransactionReceipt = async () => ({ ...receipt, logs: [{ ...log, address: EXPECTED_FUJI_ACCOUNT }] });
    await expect(verifyRegistration(rpc, hash)).rejects.toThrow(/event/i);
  });
  it("does not accept a different tokenURI on chain", async () => {
    const rpc = reader(); rpc.readContract = async args => args.functionName === "ownerOf" ? EXPECTED_FUJI_ACCOUNT : "https://attacker.invalid/agent.json";
    await expect(verifyRegistration(rpc, hash)).rejects.toThrow(/URI|read.back/i);
  });
  it("rejects mismatched sender or calldata despite a successful receipt", async () => {
    const rpc = reader(); const tx = await rpc.getTransaction();
    rpc.getTransaction = async () => ({ ...tx, input: "0x1234" });
    await expect(verifyRegistration(rpc, hash)).rejects.toThrow(/transaction/i);
  });
});
