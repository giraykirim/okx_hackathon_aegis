# AEGIS — Avalanche Fuji (Chain ID 43113) On-Chain Proof & Verification Report (`web3/PROOF.md`)

**Owner:** Person 3 (`web3/**`)  
**Rubric Category:** E. Avalanche Integration — **10 Points** (`5 pts` Deployed on C-Chain/Avalanche L1 + `5 pts` Uses Avalanche strengths)

---

## 1. Most Important Architectural Explanation (Nonnegotiable)

> **Agent reasoning/inference (LAYA operational classifier, EVREN LLM) and OKX Agent Trade Kit (ATK) market/order execution run OFF-CHAIN.**  
> **Avalanche Fuji C-Chain (`chainId = 43113`) contracts provide ONLY:**
> 1. **ERC-8004 On-Chain Agent Identity** (`agentId`, `owner`, `agentURI` / `tokenURI` pointing to the registration descriptor), and
> 2. **`RiskDecisionRegistry.sol` Audit Receipt Anchoring** (`{decisionHash, runIdHash, policyVersionHash, caller, timestamp, verdictCode}` over canonical SHA-256 digests of sanitized off-chain assessments).
>
> **Neither ERC-8004 nor `RiskDecisionRegistry.sol` executes Python policy, neural network inference, or exchange orders on the EVM.**  
> **We use Avalanche Fuji C-Chain (`43113`) only — we do NOT claim a custom Avalanche L1 or Interchain Messaging (ICM/Teleporter).**

---

## 2. Live Avalanche Fuji C-Chain (`43113`) RPC & Official ERC-8004 Registry Verification

Executed via [`web3/scripts/deploy-and-prove-fuji.ts`](./scripts/deploy-and-prove-fuji.ts) and recorded in [`web3/fuji-proof-manifest.json`](./fuji-proof-manifest.json):

| Check | Target | Result | Verifiable Link / Evidence |
|---|---|---|---|
| **RPC Network & Chain ID** | `https://api.avax-test.network/ext/bc/C/rpc` | **PASS** (`chainId = 43113`, verified at block `#59593917`) | [`web3/fuji-proof-manifest.json`](./fuji-proof-manifest.json) |
| **Official ERC-8004 `IdentityRegistry`** | `0x8004A818BFB912233c491871b3d84c89A494BD9e` | **PASS** (`eth_getCode` = 130-byte ERC-1967 proxy; `name() = "AgentIdentity"`, `symbol() = "AGENT"`, `ownerOf(1) = 0x9Dae1ef186770C059BD35ea2D23dA3a166712e04`) | [Snowtrace Fuji: `0x8004A818...4BD9e`](https://testnet.snowtrace.io/address/0x8004A818BFB912233c491871b3d84c89A494BD9e) · [Official Repo](https://github.com/erc-8004/erc-8004-contracts) |
| **Official ERC-8004 `ReputationRegistry`** | `0x8004B663056A597Dffe9eCcC1965A193B7388713` | **PASS** (`eth_getCode` = 130-byte ERC-1967 proxy) | [Snowtrace Fuji: `0x8004B663...88713`](https://testnet.snowtrace.io/address/0x8004B663056A597Dffe9eCcC1965A193B7388713) · [Official Repo](https://github.com/erc-8004/erc-8004-contracts) |

---

## 3. `RiskDecisionRegistry.sol` — Compilation, Unit Tests & Real Backend Audit Integration

### Contract Specification ([`web3/contracts/RiskDecisionRegistry.sol`](./contracts/RiskDecisionRegistry.sol))
- **Compiler:** `solc 0.8.37+commit.6e57b50f` (`evmVersion: "paris"`, optimizer enabled `200` runs)
- **Compiled Bytecode Size:** `2,135 bytes` ([`web3/artifacts/RiskDecisionRegistry.json`](./artifacts/RiskDecisionRegistry.json))
- **On-Chain Struct & Event:**
  - `struct DecisionReceipt { bytes32 decisionHash; bytes32 runIdHash; bytes32 policyVersionHash; address caller; uint64 timestamp; uint8 verdictCode; }`
  - `event DecisionReceiptRecorded(bytes32 indexed decisionHash, bytes32 indexed runIdHash, bytes32 indexed policyVersionHash, address caller, uint64 timestamp, uint8 verdictCode)`
- **Safety Guards:**
  1. **Zero Private Data:** Only `bytes32` SHA-256 / Keccak-256 hashes and integer verdict code (`0 = CLEAR_TO_PROCEED`, `1 = REVIEW`, `2 = HALT`) are stored on-chain. No API keys, balances, quantities, or customer identifiers ever touch the blockchain.
  2. **Access Control (`onlyAuthorizedEmitter`):** Only `owner` or addresses explicitly granted via `setEmitter(address, bool)` can record decision receipts; unauthorized callers revert with `UnauthorizedEmitter(caller)`.
  3. **Duplicate & Zero-Hash Guards:** Re-submitting an existing `decisionHash` reverts with `DuplicateDecisionHash(decisionHash)`; `bytes32(0)` reverts with `ZeroDecisionHash()`.

### Local EVM Unit + Backend Audit Integration Proof (`3/3 PASS`)
Executed via [`web3/tests/risk-decision-registry.test.ts`](./tests/risk-decision-registry.test.ts) on `@ethereumjs/vm`:
1. **Byte-Exact Python Audit Payload Verification:**
   - Source: [`backend/evidence/amendment-http.json`](../backend/evidence/amendment-http.json) (`excess_notional` assessment, `assessment_id = 5647b919af6e4d9b8851e8376369486e`, `assessment = HALT`).
   - Canonical JSON SHA-256 recomputed in TypeScript: `0x166c93073c84eddf94e432f3b0a52a66f60a6c308097beed0527097cfb3c08b2` (**100% byte-for-byte match** with Python `assessment_sha256`).
   - `runIdHash` (`keccak256("5647b919af6e4d9b8851e8376369486e")`): `0x6b156eb3fae9cd2dbec4ad5a614e9c6b036b0b1166ff100a616a278870a4568d`.
   - `policyVersionHash` (`keccak256("aegis.service.risk_assessment.v1")`): `0x8cf3204e7ffcf85ac7c849fb0231382df78d44c6887739db77d2eb4004c412c6`.
2. **EVM Execution & Event Decoding:**
   - Deployed `RiskDecisionRegistry.sol` in EVM, invoked `recordDecision(decisionHash, runIdHash, policyVersionHash, 2)`, decoded the emitted `DecisionReceiptRecorded` log via Viem `decodeEventLog`, and verified `getDecisionReceipt(decisionHash)` read-back (`exists = true`, `verdictCode = 2`).
3. **Access Control & Duplicate Reverts:**
   - Confirmed `DuplicateDecisionHash` revert (`0x00fa9f99`) and `UnauthorizedEmitter` revert (`0x26b7d1a5`) before granting emitter permission via `setEmitter`.

---

## 4. What These Proofs Prove vs. What Remains `NOT_TESTED`

| Capability | Current Status | What It Proves / Does Not Prove |
|---|---|---|
| **Fuji C-Chain (`43113`) RPC & Official ERC-8004 Contracts** | **PASS (Verified Live on Fuji)** | Proves official `IdentityRegistry` (`0x8004A818...4BD9e`) and `ReputationRegistry` (`0x8004B663...88713`) have live bytecode on Fuji block `#59593917` and respond to ERC-721 `name()`, `symbol()`, and `ownerOf(1)` calls. |
| **`RiskDecisionRegistry.sol` + Canonical Backend Hash** | **PASS (Local EVM `3/3 PASS`)** | Proves the Solidity contract compiles cleanly, enforces emitter access control + duplicate guards, and records/reads back the exact SHA-256 digest from Person 1's `backend/evidence/amendment-http.json`. |
| **Live Fuji Transaction Broadcast (`register(agentURI)` & `RiskDecisionRegistry` deploy)** | **`NOT_TESTED` (`verified=false`)** | Requires a disposable Fuji wallet funded with testnet AVAX (`FUJI_PRIVATE_KEY`) and a public HTTPS `AEGIS_PUBLIC_AGENT_URI`. We never fabricate `agentId`, contract addresses, transaction hashes, confirmation times, or gas fees. |
| **ERC-8004 Reputation Registry Writes** | **Intentionally Omitted** | Per Prompt 00 rules: read-only reputation queries are allowed; fake or self-awarded reputation feedback is strictly forbidden. |

### One-Command Live Fuji Broadcast (Once Disposable Test Wallet Has Faucet AVAX)
```bash
cd web3
FUJI_PRIVATE_KEY=0x<disposable_fuji_test_key> \
AEGIS_PUBLIC_AGENT_URI=https://<public-host>/.well-known/erc8004-agent.json \
npm run prove:fuji
```
This script automatically:
1. Checks `chainId == 43113` and wallet AVAX balance,
2. Deploys `RiskDecisionRegistry.sol` to Fuji and measures confirmation time (`ms`) and actual fee (`AVAX`),
3. Submits `recordDecision(...)` with the real backend `decisionHash` (`0x166c9307...`) and reads back `getDecisionReceipt(decisionHash)`,
4. Calls `IdentityRegistry.register(AEGIS_PUBLIC_AGENT_URI)`, extracts `agentId` from the `Transfer` receipt log, reads back `ownerOf(agentId)` and `tokenURI(agentId)`, and writes all verified hashes/timestamps into `web3/fuji-proof-manifest.json`.

---

## 5. Question for Hackathon Mentors / Judges (Bonus Criteria Confirmation)
> *"For the 10-point Avalanche Integration rubric (5 pts C-Chain/L1 deployment + 5 pts use of Avalanche strengths), does combining (1) official ERC-8004 `IdentityRegistry` registration (`0x8004A818BFB912233c491871b3d84c89A494BD9e`) on Fuji C-Chain with (2) our custom `RiskDecisionRegistry.sol` contract anchoring canonical SHA-256 pre-trade risk decision receipts satisfy the full C-Chain utility criteria, given that LLM/ATK execution intentionally runs off-chain for security?"*
