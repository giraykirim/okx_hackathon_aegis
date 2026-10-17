# ERC-8004 MetaMask Registration Plan

**Goal:** Register AEGIS on the official Fuji IdentityRegistry using the already published public metadata and the user's funded MetaMask account, then verify and persist the actual identity.

**Architecture:** Reuse EIP-6963 provider selection, Fuji-only account checks, bounded zero-value transaction fees and durable per-intent browser journals. Add the fixed `register(agentURI)` intent and strict receipt/event/owner/tokenURI verifier. A read-only metadata preflight supplies the current public descriptor; minting is blocked for an already-owned identity. No local server key, exchange order or `ml/**` edit is involved.

1. Execute a real read-only owner balance preflight (zero identities observed).
2. Write failing tests for fixed calldata, existing identity, wrong chain, reverted/mismatched receipt/event/URI; implement and run them.
3. Add the public metadata preflight and a separate MetaMask registration button, with recheck/recovery using the actual hash and no automatic retry.
4. Request the user's native MetaMask transaction approval only after the concrete preflight is reviewable.
5. Independently verify the confirmed transaction and Registered event; persist actual agent ID/owner/URI/fees, update metadata registrations with that observed ID, and verify the updated public bytes.
6. Configure and verify the dashboard read-back, run appropriate tests/type/lint/contract checks, and report the real on-chain proof.
