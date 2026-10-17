import { decodeEventLog, encodeFunctionData, parseAbi, type Address, type Hex } from "viem";
import { EXPECTED_FUJI_ACCOUNT, type FujiTransaction } from "./fuji-wallet";

export const IDENTITY_REGISTRY = "0x8004A818BFB912233c491871b3d84c89A494BD9e" as const;
export const AGENT_METADATA_URI = "https://gist.githubusercontent.com/giraykirim/367b45ff5fce169bf1e7a1447eb88d91/raw/agent-registration.json";
export const IDENTITY_ABI = parseAbi([
  "function register(string agentURI) returns (uint256 agentId)",
  "function ownerOf(uint256 tokenId) view returns (address)",
  "function tokenURI(uint256 tokenId) view returns (string)",
  "function balanceOf(address owner) view returns (uint256)",
  "event Registered(uint256 indexed agentId, string agentURI, address indexed owner)",
]);
const same = (a: string, b: string) => a.toLowerCase() === b.toLowerCase();

export function registrationTransaction(): FujiTransaction {
  return { from: EXPECTED_FUJI_ACCOUNT, to: IDENTITY_REGISTRY, data: encodeFunctionData({ abi: IDENTITY_ABI, functionName: "register", args: [AGENT_METADATA_URI] }), value: "0x0", chainId: "0xa869", gas: "0x7a120", maxFeePerGas: "0x5d21dba00", maxPriorityFeePerGas: "0x3b9aca00" };
}

interface IdentityReader {
  getChainId(): Promise<number>;
  getCode(args: { address: Address }): Promise<string | undefined>;
  readContract(args: { address: typeof IDENTITY_REGISTRY; abi: typeof IDENTITY_ABI; functionName: "balanceOf" | "ownerOf" | "tokenURI"; args: readonly [Address | bigint] }): Promise<unknown>;
  getTransactionReceipt(args: { hash: Hex }): Promise<{ status: string; blockNumber: bigint; gasUsed: bigint; effectiveGasPrice: bigint; logs: readonly { address: string; data: Hex; topics: readonly Hex[] }[] }>;
  getTransaction(args: { hash: Hex }): Promise<{ from: string; to: string | null; value: bigint; input: string }>;
}

export async function assertUnregistered(client: Pick<IdentityReader, "getChainId" | "getCode" | "readContract">) {
  if (await client.getChainId() !== 43113) throw new Error("Fuji network required; mint blocked.");
  const code = await client.getCode({ address: IDENTITY_REGISTRY });
  if (!code || code === "0x") throw new Error("Official registry bytecode unavailable; mint blocked.");
  const balance = await client.readContract({ address: IDENTITY_REGISTRY, abi: IDENTITY_ABI, functionName: "balanceOf", args: [EXPECTED_FUJI_ACCOUNT] });
  if (typeof balance !== "bigint" || balance !== BigInt(0)) throw new Error("Existing identity found for this account; verify it instead of minting again.");
}

export interface RegistrationProof {
  chainId: 43113;
  registryAddress: typeof IDENTITY_REGISTRY;
  agentId: string;
  owner: Address;
  agentURI: typeof AGENT_METADATA_URI;
  registrationTxHash: Hex;
  explorerUrl: string;
  verified: true;
  verification_status: "VERIFIED_ON_CHAIN";
  checkedAt: string;
  blockNumber: string;
  gas_used: string;
  effective_gas_price_wei: string;
  fee_wei: string;
}

export async function verifyRegistration(client: IdentityReader, hash: Hex): Promise<RegistrationProof> {
  if (!/^0x[\da-f]{64}$/i.test(hash) || await client.getChainId() !== 43113) throw new Error("Valid Fuji registration transaction required.");
  const receipt = await client.getTransactionReceipt({ hash });
  if (receipt.status !== "success") throw new Error("Registration transaction reverted.");
  const tx = await client.getTransaction({ hash });
  if (!same(tx.from, EXPECTED_FUJI_ACCOUNT) || !tx.to || !same(tx.to, IDENTITY_REGISTRY) || tx.value !== BigInt(0) || !same(tx.input, registrationTransaction().data)) throw new Error("Registration transaction differs from the reviewed account, registry or URI.");
  const events: { agentId: bigint; owner: Address; agentURI: string }[] = [];
  for (const log of receipt.logs) {
    if (!same(log.address, IDENTITY_REGISTRY)) continue;
    try {
      const event = decodeEventLog({ abi: IDENTITY_ABI, eventName: "Registered", data: log.data, topics: [...log.topics] as [Hex, ...Hex[]] });
      events.push(event.args);
    } catch { /* unrelated registry event */ }
  }
  if (events.length !== 1 || !same(events[0].owner, EXPECTED_FUJI_ACCOUNT) || events[0].agentURI !== AGENT_METADATA_URI) throw new Error("A unique matching Registered event is required.");
  const id = events[0].agentId;
  const [owner, uri, code] = await Promise.all([
    client.readContract({ address: IDENTITY_REGISTRY, abi: IDENTITY_ABI, functionName: "ownerOf", args: [id] }),
    client.readContract({ address: IDENTITY_REGISTRY, abi: IDENTITY_ABI, functionName: "tokenURI", args: [id] }),
    client.getCode({ address: IDENTITY_REGISTRY }),
  ]);
  if (!code || code === "0x" || typeof owner !== "string" || !same(owner, EXPECTED_FUJI_ACCOUNT) || uri !== AGENT_METADATA_URI) throw new Error("Registration owner/URI read-back mismatch.");
  return { chainId: 43113, registryAddress: IDENTITY_REGISTRY, agentId: id.toString(), owner: owner as Address, agentURI: AGENT_METADATA_URI, registrationTxHash: hash, explorerUrl: `https://testnet.snowtrace.io/tx/${hash}`, verified: true, verification_status: "VERIFIED_ON_CHAIN", checkedAt: new Date().toISOString(), blockNumber: receipt.blockNumber.toString(), gas_used: receipt.gasUsed.toString(), effective_gas_price_wei: receipt.effectiveGasPrice.toString(), fee_wei: (receipt.gasUsed * receipt.effectiveGasPrice).toString() };
}
