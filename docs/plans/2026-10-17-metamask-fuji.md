# MetaMask Fuji Signing Implementation Plan

**Goal:** Connect the user's funded MetaMask account to the existing Avalanche page and prepare separate user-approved Fuji deployment and receipt transactions without copying a private key.

**Architecture:** An additive read-only Next.js endpoint serves the existing compiled registry artifact and a recorded backend HALT digest. A browser component requests account access, explicitly switches to Fuji, and exposes separate deployment/receipt actions with zero AVAX transfer value and bounded gas fees. Submitted transaction hashes and uncertain submission states survive reload; receipts and runtime bytecode are checked independently before showing verified. Existing API contracts, identity claims and `ml/**` remain unchanged. Continue in the same checkout as requested.

**Tech Stack:** Next.js client component/route handler, existing viem ABI encoding and Fuji public client, EIP-1193 MetaMask provider, Vitest.

1. Read the installed Next.js client/route guidance and current web3 artifact, ABI, verifier and tests.
2. Write and execute failing tests for missing wallet, wrong account/network, wallet refusal, successful Fuji switching, no send on connection, duplicate/ambiguous submission prevention, and reverted/mismatched confirmation.
3. Implement the smallest wallet helper and unsigned deployment-plan route; return only public contract/assessment information.
4. Add a distinct MetaMask panel to `/avalanche`; no writes on mount/connect. Offer separate Deploy and Record buttons, honest status and recovery/read-only checks. Keep ERC-8004 identity pending until a public URI and actual registration exist.
5. Execute frontend tests, TypeScript and relevant lint, local EVM tests and actual HTTP/UI smoke. No claim of live MetaMask signature or deploy without the user's wallet confirmation.
6. Document exact browser and signing steps and preserve all unrelated changes.
