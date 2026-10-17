# MetaMask Fuji signing

The `/avalanche` page now supports the operator's funded test account `0x3754131A55d043fC49eB93cEBfB381953cA41bB8` through its injected MetaMask provider. No private-key export/import is required. The independently generated local `web3/.env` wallet is a different, unused account; it is not used by this browser flow.

1. Open `http://127.0.0.1:3000/avalanche` in the browser containing MetaMask (currently Opera).
2. Select **Connect MetaMask** and approve account access for the expected test account. Approve the Fuji network switch/addition if requested. Connection performs no transaction submission.
3. Inspect **Review unsigned plan**. The read-only `/api/web3/deployment-plan` endpoint supplies the existing compiled `RiskDecisionRegistry` bytecode, its expected runtime bytecode and the byte-exact SHA-256 digest of the recorded backend HALT assessment in `backend/evidence/amendment-http.json`. `web3/artifacts/receipt-assessment.json` preserves the exact canonical bytes exported from Python; mismatched evidence fails closed. This is a recorded assessment, not a fresh market signal.
4. **1. Deploy receipt contract** opens one separate MetaMask transaction confirmation. Value is zero; gas is capped at 1,000,000 and max fee at 25 gwei (maximum 0.025 test AVAX before any edits in MetaMask). Mainnet and a different account are blocked immediately before submission.
5. Wait for independent public Fuji read-back of transaction receipt, input, sender, bytecode and contract owner. If confirmation is unavailable, choose **Recheck deploy transaction**; never send a duplicate deployment to recover a timeout.
6. **2. Record HALT receipt** opens a second separate MetaMask confirmation. Gas is capped at 250,000 and max fee at 25 gwei (maximum 0.00625 test AVAX before wallet edits). The fixed receipt commits only digest/run/policy hashes and verdict 2 (HALT), never model inputs or private account data.
7. Independent read-back must match all receipt fields before VERIFIED is shown. Download the deploy/record proof JSON for the jury. The existing verifier is updated with the actual contract address and digest after successful receipt verification.

Submission attempts are journaled in browser localStorage before requesting a signature. Hashes survive reload. A deliberate wallet rejection permits another explicit attempt; an ambiguous error or pending/submitted transaction blocks resubmission. The browser Web Locks API serializes signing across same-origin tabs. There is no automatic transaction retry. If no hash was returned, inspect MetaMask Activity and resolve the venue state before any further write; do not clear the journal to force a retry.

The in-app browser may not expose MetaMask; use its installed browser. A fresh standalone deployment containing only `frontend/` needs the two public web3 artifacts and backend assessment evidence packaged at the documented sibling paths; otherwise plan serving returns 503 and signing stays disabled.

ERC-8004 Agent #273 is now registered with the public Gist metadata URI; see `web3/registration-proof.json`. Receipt deployment does not register an agent and does not grant exchange execution permission. Existing FastAPI contracts and `ml/**` are unchanged.

Executed validation: 31 frontend tests passed; TypeScript and targeted lint checks passed. Three existing local EVM tests passed again for this change. The plan endpoint and `/avalanche` returned HTTP 200. Live MetaMask account approval, deployment and receipt transaction status must be checked separately; passing automated tests does not establish a live on-chain deployment.

The first real Opera connection attempt exposed a multi-wallet collision: another extension's provider advertised `isMetaMask` and returned `Broadcast channel unavailable`. The panel now uses EIP-6963 discovery with MetaMask's `io.metamask` provider announcement, covered by two regression tests. After that fix, the account request was restarted through the specifically discovered provider; native MetaMask account/network approval remains a user step. No transaction button was clicked during UI verification.

## Actual signed Fuji result

The user then approved the actual MetaMask connection and both separate Fuji transactions. Deployment and HALT receipt verification are **PASS** at contract `0x5ae5642cd6a02e0834b3fba822d442429aeadc5f`; see `web3/metamask-fuji-proof.json` and `web3/PROOF.md` for hashes, block numbers and actual fees. The browser proof download automation timed out; a separate read-only RPC verifier exported the proof without requesting private keys or sending another transaction. `web3/scripts/verify-metamask.ts` is the reproducible post-confirmation check. Native extension pages are blocked by the browser URL policy; all extension approvals were completed by the user.

The local frontend's ignored environment file now supplies the verified registry address and sample digest for `/api/web3/verify`. On other machines configure `RISK_DECISION_REGISTRY_ADDRESS` and `RISK_DECISION_SAMPLE_SHA256` from the verified proof. FastAPI identity and assessment `chain_receipt` fields remain unchanged; this browser-selected recorded assessment proof does not automatically attach receipts to unrelated service responses.

Commands from `frontend/`: `npx vitest run`, `npx tsc --noEmit`, targeted `npx eslint` on the changed wallet, plan, page and test files. From `web3/`: `npm test`.

## Confirmed ERC-8004 registration

The user approved the separate **3. Register ERC-8004 identity** transaction. The fixed call transferred zero AVAX, with a 500,000 gas / 25 gwei cap (maximum 0.0125 test AVAX). The actual transaction is `0x7b61d86a11c815b301d44d6062c938bd7c8995c9d81332f9bb476c0bc436f08b`, block 59600465, fee 0.0002500000025 test AVAX. Independent verification exported Agent #273, the expected owner and exact public tokenURI. Reputation read returned zero independent feedback; no feedback was created.

The registration panel rechecks public metadata bytes against the publication hash and refuses minting when the account already owns an identity. Recovery accepts an actual transaction hash and only reads chain state. The local frontend uses a read-only `FUJI_RPC_URL` override after the official endpoint returned HTTP 429; every readback still checks chain 43113. Signing stays through MetaMask, without key export. The frontend BFF presents fresh RPC verification; backend frozen DTOs are unchanged.
