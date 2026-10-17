export const FUJI_CHAIN_ID = 43113 as const;
export const FUJI_RPC_DEFAULT = "https://api.avax-test.network/ext/bc/C/rpc";
export const FUJI_EXPLORER_TX_BASE = "https://testnet.snowtrace.io/tx/";
export const FUJI_EXPLORER_ADDRESS_BASE = "https://testnet.snowtrace.io/address/";

/**
 * Official ERC-8004 Registry Addresses on Avalanche Fuji Testnet (Chain ID 43113)
 * Verified against https://github.com/erc-8004/erc-8004-contracts and live `eth_getCode` on Fuji 43113.
 */
export const OFFICIAL_FUJI_ERC8004_IDENTITY_REGISTRY =
  "0x8004A818BFB912233c491871b3d84c89A494BD9e" as const;
export const OFFICIAL_FUJI_ERC8004_REPUTATION_REGISTRY =
  "0x8004B663056A597Dffe9eCcC1965A193B7388713" as const;

/**
 * Official ERC-8004 IdentityRegistryUpgradeable ABI (from erc-8004/erc-8004-contracts).
 * Note: ERC-8004 registers an agentId and agentURI (tokenURI) on-chain.
 * It does NOT run Python, LAYA, or EVREN on the EVM.
 */
export const ERC8004_IDENTITY_REGISTRY_ABI = [
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
    name: "register",
    stateMutability: "nonpayable",
    inputs: [{ name: "agentURI", type: "string" }],
    outputs: [{ name: "agentId", type: "uint256" }],
  },
  {
    type: "function",
    name: "setAgentURI",
    stateMutability: "nonpayable",
    inputs: [
      { name: "agentId", type: "uint256" },
      { name: "newURI", type: "string" },
    ],
    outputs: [],
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
  {
    type: "function",
    name: "getMetadata",
    stateMutability: "view",
    inputs: [
      { name: "agentId", type: "uint256" },
      { name: "metadataKey", type: "string" },
    ],
    outputs: [{ name: "", type: "bytes" }],
  },
  {
    type: "event",
    name: "Registered",
    inputs: [
      { indexed: true, name: "agentId", type: "uint256" },
      { indexed: false, name: "agentURI", type: "string" },
      { indexed: true, name: "owner", type: "address" },
    ],
  },
  {
    type: "event",
    name: "URIUpdated",
    inputs: [
      { indexed: true, name: "agentId", type: "uint256" },
      { indexed: false, name: "newURI", type: "string" },
      { indexed: true, name: "updatedBy", type: "address" },
    ],
  },
] as const;

/**
 * Official ERC-8004 ReputationRegistryUpgradeable Read-Only ABI (from erc-8004/erc-8004-contracts).
 * Note: Self-awarded feedback is strictly forbidden. Used only for read-only verification.
 */
export const ERC8004_REPUTATION_REGISTRY_ABI = [
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

/**
 * ABI for AEGIS RiskDecisionRegistry.sol on Avalanche Fuji (43113).
 * Stores sanitized canonical digests (`{decisionHash, runIdHash, policyVersionHash, caller, timestamp, verdictCode}`).
 */
export const RISK_DECISION_REGISTRY_ABI = [
  {
    type: "constructor",
    inputs: [],
    stateMutability: "nonpayable",
  },
  {
    type: "function",
    name: "VERDICT_REVIEW",
    stateMutability: "view",
    inputs: [],
    outputs: [{ name: "", type: "uint8" }],
  },
  {
    type: "function",
    name: "VERDICT_HALT",
    stateMutability: "view",
    inputs: [],
    outputs: [{ name: "", type: "uint8" }],
  },
  {
    type: "function",
    name: "VERDICT_VETOED_NO_TRADE",
    stateMutability: "view",
    inputs: [],
    outputs: [{ name: "", type: "uint8" }],
  },
  {
    type: "function",
    name: "owner",
    stateMutability: "view",
    inputs: [],
    outputs: [{ name: "", type: "address" }],
  },
  {
    type: "function",
    name: "authorizedEmitters",
    stateMutability: "view",
    inputs: [{ name: "emitter", type: "address" }],
    outputs: [{ name: "", type: "bool" }],
  },
  {
    type: "function",
    name: "setAuthorizedEmitter",
    stateMutability: "nonpayable",
    inputs: [
      { name: "emitter", type: "address" },
      { name: "authorized", type: "bool" },
    ],
    outputs: [],
  },
  {
    type: "function",
    name: "transferOwnership",
    stateMutability: "nonpayable",
    inputs: [{ name: "newOwner", type: "address" }],
    outputs: [],
  },
  {
    type: "function",
    name: "recordDecision",
    stateMutability: "nonpayable",
    inputs: [
      { name: "decisionHash", type: "bytes32" },
      { name: "runIdHash", type: "bytes32" },
      { name: "policyVersionHash", type: "bytes32" },
      { name: "verdictCode", type: "uint8" },
    ],
    outputs: [],
  },
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
  {
    type: "function",
    name: "totalReceipts",
    stateMutability: "view",
    inputs: [],
    outputs: [{ name: "", type: "uint256" }],
  },
  {
    type: "function",
    name: "decisionHashAt",
    stateMutability: "view",
    inputs: [{ name: "index", type: "uint256" }],
    outputs: [{ name: "", type: "bytes32" }],
  },
  {
    type: "event",
    name: "DecisionReceiptRecorded",
    inputs: [
      { indexed: true, name: "decisionHash", type: "bytes32" },
      { indexed: true, name: "runIdHash", type: "bytes32" },
      { indexed: true, name: "policyVersionHash", type: "bytes32" },
      { indexed: false, name: "caller", type: "address" },
      { indexed: false, name: "timestamp", type: "uint64" },
      { indexed: false, name: "verdictCode", type: "uint8" },
    ],
  },
  {
    type: "event",
    name: "EmitterAuthorizationChanged",
    inputs: [
      { indexed: true, name: "emitter", type: "address" },
      { indexed: false, name: "authorized", type: "bool" },
    ],
  },
  {
    type: "event",
    name: "OwnershipTransferred",
    inputs: [
      { indexed: true, name: "previousOwner", type: "address" },
      { indexed: true, name: "newOwner", type: "address" },
    ],
  },
  {
    type: "error",
    name: "UnauthorizedCaller",
    inputs: [{ name: "caller", type: "address" }],
  },
  {
    type: "error",
    name: "ZeroHashNotAllowed",
    inputs: [],
  },
  {
    type: "error",
    name: "DuplicateDecisionHash",
    inputs: [{ name: "decisionHash", type: "bytes32" }],
  },
  {
    type: "error",
    name: "InvalidVerdictCode",
    inputs: [{ name: "verdictCode", type: "uint8" }],
  },
  {
    type: "error",
    name: "InvalidAddress",
    inputs: [],
  },
] as const;
