# AEGIS — Avalanche Fuji (Chain ID 43113) Identity & Receipt Contracts (`web3/`)

Owned by **Person 3** (`web3/**`). See [`PROOF.md`](./PROOF.md) for the complete verification report and Snowtrace links.

## Verified MetaMask Fuji update — 2026-10-17

The operator signed three real Fuji transactions through `/avalanche` using MetaMask account `0x3754131A55d043fC49eB93cEBfB381953cA41bB8`. `RiskDecisionRegistry` is deployed at `0x5ae5642cd6a02e0834b3fba822d442429aeadc5f`; the recorded backend HALT digest is anchored and independently verified. See [`metamask-fuji-proof.json`](./metamask-fuji-proof.json), the updated [`fuji-proof-manifest.json`](./fuji-proof-manifest.json), and [browser signing instructions](../docs/product/METAMASK_FUJI.md). ERC-8004 **Agent #273 is registered and independently verified**, including the actual Registered event, owner and public tokenURI. See [`registration-proof.json`](./registration-proof.json).

Reproduce the actual proof with this **read-only** command (no key needed):

```sh
./node_modules/.bin/tsx scripts/verify-metamask.ts \
  --deploy-tx 0x7cb24d8f07bf936d5b2224e047690b114102221369339b1a44cd412cd0db7ba3 \
  --record-tx 0xcb226fb049a7052ca8889d585dfcb3a1cf66528e318a60c7ff2c9b43a67de2f1
```

Reproduce identity verification without a key or new transaction:

```sh
FUJI_RPC_URL=https://avalanche-fuji-c-chain-rpc.publicnode.com \
./node_modules/.bin/tsx scripts/verify-identity-metamask.ts \
  --tx 0x7b61d86a11c815b301d44d6062c938bd7c8995c9d81332f9bb476c0bc436f08b
```

The official Avalanche public RPC returned HTTP 429 during verification. The read-only verifier and local frontend accept `FUJI_RPC_URL`; independent verification succeeded through PublicNode Fuji after checking chain ID 43113. No write is retried on RPC failure. The frontend BFF freshly verifies chain data; the frozen FastAPI identity DTO remains unchanged. Public metadata advertises no available public API (`active=false`, `services=[]`).

The `.env` disposable key generated earlier belongs to a different unused wallet. It is not the MetaMask signing account. The legacy `prove:fuji` script below is a separate server-key deployment workflow, not the verification command for this MetaMask deployment; running it can submit new transactions or replace its manifest. Use the read-only command above for the jury replay.

## Nonnegotiable Architectural Boundary
- **Off-Chain Runtime (M2 FastAPI + Official OKX ATK CLI + RTX 4070 LAN):**
  - Deterministic Python risk policy, official `@okx_ai/okx-trade-cli@1.4.8` subprocess observations, LAYA operational classifier (`CONTINUE` / `REVIEW` / `HALT`), and EVREN bounded reasoning all execute **OFF-CHAIN**.
- **On-Chain Identity & Audit Anchoring (Avalanche Fuji C-Chain `chainId = 43113`):**
  1. **Official ERC-8004 `IdentityRegistry` (`0x8004A818BFB912233c491871b3d84c89A494BD9e`):** Registers `agentId` and `agentURI` (`tokenURI`) pointing to the public `/agent-registration.json` descriptor. Bytecode verified live on Fuji (`130 bytes`, `name()="AgentIdentity"`, `symbol()="AGENT"`).
  2. **Official ERC-8004 `ReputationRegistry` (`0x8004B663056A597Dffe9eCcC1965A193B7388713`):** Bytecode and `getIdentityRegistry()` verified live on Fuji (`130 bytes`). Read-only lookup returns `"No independent feedback yet"`; self-awarded feedback is strictly forbidden.
  3. **`RiskDecisionRegistry.sol` ([`contracts/RiskDecisionRegistry.sol`](./contracts/RiskDecisionRegistry.sol)):** Independently compiled (`solc 0.8.37`, `2,135 bytes`) utility contract that maps and emits `{decisionHash, runIdHash, policyVersionHash, caller, timestamp, verdictCode}` for canonical SHA-256 digests of off-chain AEGIS risk assessments. Zero private keys, balances, or portfolio inputs are ever stored on-chain.

## Directory Contents
- [`.env.example`](./.env.example) — Variable names only (`FUJI_RPC_URL`, `FUJI_TEST_WALLET_PRIVATE_KEY`, `AGENT_REGISTRATION_URI`); `.env` is gitignored.
- [`scripts/probe.ts`](./scripts/probe.ts) — **PROMPT 10** probe script verifying `eth_chainId == 43113`, `getCode` on both official ERC-8004 registries, `simulateContract` dry-run for `register(string agentURI)`, and schema validation for `agent-registration.template.json`.
- [`scripts/register-and-verify.ts`](./scripts/register-and-verify.ts) — **PROMPT 11 & 12** idempotent registration & verification script that parses `Registered(uint256 agentId, string agentURI, address owner)`, reads back `ownerOf(agentId)` + `tokenURI(agentId)` + `ReputationRegistry` summary, and writes [`registration-proof.json`](./registration-proof.json).
- [`scripts/deploy-and-prove-fuji.ts`](./scripts/deploy-and-prove-fuji.ts) — Deploys `RiskDecisionRegistry.sol` and records the canonical backend decision receipt on Fuji when funded, writing [`fuji-proof-manifest.json`](./fuji-proof-manifest.json).
- [`scripts/compile.ts`](./scripts/compile.ts) — Compiles `RiskDecisionRegistry.sol` into [`artifacts/RiskDecisionRegistry.json`](./artifacts/RiskDecisionRegistry.json).
- [`scripts/verify-fuji.ts`](./scripts/verify-fuji.ts) — Standalone read-only Viem verifier.
- [`agent-registration.template.json`](./agent-registration.template.json) & [`erc8004-registration.template.json`](./erc8004-registration.template.json) — ERC-8004 v1 registration JSON templates (`services: []`, `x402Support: false`, `active: true`, `registrations: []`).
- [`registration-proof.json`](./registration-proof.json) & [`fuji-proof-manifest.json`](./fuji-proof-manifest.json) — Machine-readable actual Fuji verification proofs (`verified: true`), with confirmation latency explicitly unmeasured.
- [`tests/risk-decision-registry.test.ts`](./tests/risk-decision-registry.test.ts) — Local EVM (`@ethereumjs/vm`) unit + backend audit integration suite (`3/3 PASS`).
- [`PROOF.md`](./PROOF.md) — Detailed proof report, Snowtrace links, and mentor bonus confirmation note.

## Commands
```bash
cd web3
npm run probe        # Probe Fuji 43113 RPC, official ERC-8004 bytecode, dry-run register(), and validate JSON schema
npm run register     # Idempotent ERC-8004 register/verify + ReputationRegistry read-back -> registration-proof.json
npm run compile      # Compile RiskDecisionRegistry.sol -> artifacts/RiskDecisionRegistry.json
npm test             # Run 3/3 EVM unit + backend audit hash integration tests
npm run prove:fuji   # Full Fuji proof manifest generator -> fuji-proof-manifest.json
```
