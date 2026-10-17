# AEGIS — verified Avalanche Fuji identity and receipt proof

Verified on 2026-10-17. Network: Fuji C-Chain, chain ID **43113**. All three transactions were individually approved by the operator through MetaMask account `0x3754131A55d043fC49eB93cEBfB381953cA41bB8`. No private key was exported and no exchange order was sent.

| Capability | Actual result | Evidence |
|---|---|---|
| Official ERC-8004 registration | PASS · Agent **273**, block **59600465** | [Registration transaction](https://testnet.snowtrace.io/tx/0x7b61d86a11c815b301d44d6062c938bd7c8995c9d81332f9bb476c0bc436f08b) · `registration-proof.json` |
| Registration ownership and metadata | PASS · matching Registered event, reviewed calldata, ownerOf(273), tokenURI(273), registry bytecode | `scripts/verify-identity-metamask.ts` |
| Public metadata | PASS · unauthenticated HTTP 200, matching reviewed JSON bytes, actual registrations entry | `metadata-publication.json` · [Agent URI](https://gist.githubusercontent.com/giraykirim/367b45ff5fce169bf1e7a1447eb88d91/raw/agent-registration.json) |
| Receipt contract deployment | PASS · `0x5ae5642cd6a02e0834b3fba822d442429aeadc5f`, block 59599560 | [Deploy transaction](https://testnet.snowtrace.io/tx/0x7cb24d8f07bf936d5b2224e047690b114102221369339b1a44cd412cd0db7ba3) · `metamask-fuji-proof.json` |
| Recorded HALT receipt | PASS · block 59599653, verdict code 2 | [Record transaction](https://testnet.snowtrace.io/tx/0xcb226fb049a7052ca8889d585dfcb3a1cf66528e318a60c7ff2c9b43a67de2f1) · `fuji-proof-manifest.json` |
| Independent reputation read | PASS · 0 third-party feedback entries | `registration-proof.json`; no feedback created |
| Public assessment API | NOT_DEPLOYED | Descriptor retains `active=false`, `services=[]` |
| Confirmation latency | NOT_MEASURED | Verification was post-confirmation; no timing claim |

Actual fees: registration **0.0002500000025**, deployment **0.0005266300052663**, HALT record **0.00016229800162298** test AVAX. Gas use and effective gas price are recorded in the proof JSON files.

Official IdentityRegistry: `0x8004A818BFB912233c491871b3d84c89A494BD9e`. Official ReputationRegistry: `0x8004B663056A597Dffe9eCcC1965A193B7388713`. [Official contract repository](https://github.com/erc-8004/erc-8004-contracts).

The anchored digest is `0x0fa71a805298f0f63ce6b994a9aa12bdc7a22e8560d903ef13cd6556ec3e6d26` from `backend/evidence/amendment-http.json:checks.excess_notional.response`. Assessment/run ID: `ec5e01df704549e2a67890e4c0852b50`. Independent receipt verification checks sender, zero transfer value, exact transaction input, compiled runtime bytecode, contract owner, stored decision/run/policy hashes, caller and HALT verdict. This is a recorded backend assessment, not a fresh trading signal.

## Reproduce without signing

From `web3/`, run:

```sh
FUJI_RPC_URL=https://avalanche-fuji-c-chain-rpc.publicnode.com \
./node_modules/.bin/tsx scripts/verify-identity-metamask.ts \
  --tx 0x7b61d86a11c815b301d44d6062c938bd7c8995c9d81332f9bb476c0bc436f08b

./node_modules/.bin/tsx scripts/verify-metamask.ts \
  --deploy-tx 0x7cb24d8f07bf936d5b2224e047690b114102221369339b1a44cd412cd0db7ba3 \
  --record-tx 0xcb226fb049a7052ca8889d585dfcb3a1cf66528e318a60c7ff2c9b43a67de2f1

npm test
```

The official Avalanche public endpoint returned HTTP 429 during the identity check; read-only verification succeeded using the Fuji endpoint advertised by [PublicNode](https://publicnode.com). Every verification checks chain 43113. Do not recover a read failure by submitting another transaction. The local frontend BFF accepts `FUJI_RPC_URL` and freshly checks the saved registration transaction before showing VERIFIED. Frozen FastAPI contracts remain unchanged.

## Executed checks

- `frontend/`: `npx vitest run` — **43 passed**; `npx tsc --noEmit` and targeted ESLint — exit 0.
- `web3/`: `npm test` — **3 passed**, including local EVM receipt events, access control, duplicate rejection and byte-exact backend assessment hashing. Compiler: `solc 0.8.37+commit.f401782d`, creation bytecode 2,135 bytes.
- `backend/`: `uv run python -m scripts.export_contract --check` — PASS, frozen v2 unchanged and additive service contract matches.
- Local HTTP `/api/web3/identity` and `/api/web3/verify` — 200; Agent #273 and stored HALT receipt independently verified.

## Architecture and scope

Python policy, EVREN reasoning, LAYA classification and official OKX ATK observations execute **off-chain**. Fuji stores the ERC-8004 identity and hash receipts. It does not run model inference, certify model correctness, or authorize exchange orders. This deployment uses Fuji C-Chain; no custom Avalanche L1 or interchain messaging is claimed. Final rubric scoring remains with the jury. `ml/**` was not edited.
