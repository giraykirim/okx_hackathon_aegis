"use client";

import React from "react";
import { createPublicClient, formatEther, http, type Hex } from "viem";
import { avalancheFuji } from "viem/chains";
import { discoverMetaMask } from "@/lib/metamask-provider";
import { connectFuji, EXPECTED_FUJI_ACCOUNT, FUJI_RPC, loadOperation, sendFujiTransaction, type Operation, type WalletProvider } from "@/lib/fuji-wallet";
import { AGENT_METADATA_URI, assertUnregistered, IDENTITY_REGISTRY, registrationTransaction, verifyRegistration, type RegistrationProof } from "@/lib/fuji-identity";

const rpc = createPublicClient({ chain: avalancheFuji, transport: http(FUJI_RPC, { timeout: 8000, retryCount: 0 }) });
interface Plan { agent_uri: string; metadata_verified: boolean; owned_identity_count: string; registered: RegistrationProof | null }
async function preflight(): Promise<Plan> {
  const response = await fetch("/api/web3/registration-plan", { cache: "no-store" });
  if (!response.ok) throw new Error("Public metadata or Fuji preflight unavailable; identity signing disabled.");
  const plan: Plan = await response.json();
  if (plan.agent_uri !== AGENT_METADATA_URI || plan.metadata_verified !== true || !/^\d+$/.test(plan.owned_identity_count)) throw new Error("Unexpected identity registration plan; signing disabled.");
  return plan;
}

export function FujiIdentityPanel({ onRegistered }: { onRegistered: (proof: RegistrationProof) => void }) {
  const provider = React.useRef<WalletProvider | undefined>(undefined);
  const lock = React.useRef(false);
  const [plan, setPlan] = React.useState<Plan | null>(null);
  const [operation, setOperation] = React.useState<Operation | null>(null);
  const [proof, setProof] = React.useState<RegistrationProof | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [notice, setNotice] = React.useState("Checking the public metadata and Fuji registration state…");
  const [recoveryHash, setRecoveryHash] = React.useState("");
  React.useEffect(() => {
    let active = true;
    const discovery = discoverMetaMask(window, next => { provider.current = next; });
    preflight().then(next => {
      if (!active) return;
      setPlan(next); setOperation(loadOperation(localStorage, registrationTransaction()));
      if (next.registered) { setProof(next.registered); onRegistered(next.registered); setNotice("Existing AEGIS identity independently verified. No new mint will be sent."); }
      else setNotice(next.owned_identity_count === "0" ? "Public metadata verified. Registering requires one separate MetaMask approval on Fuji." : "Existing identity detected; mint disabled. Recheck its actual transaction hash.");
    }).catch(error => { if (active) setNotice(error instanceof Error ? error.message : "Identity preflight unavailable."); });
    return () => { active = false; discovery.stop(); provider.current = undefined; };
    // Mount performs only public reads. The callback only publishes a verified result.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function guarded(work: () => Promise<void>) {
    if (lock.current) return;
    lock.current = true; setBusy(true);
    try { await work(); } catch (error) { setNotice(error instanceof Error ? error.message : "Registration unavailable; no automatic retry."); }
    finally { lock.current = false; setBusy(false); }
  }
  async function check(hash: string, wait = false) {
    if (!/^0x[\da-f]{64}$/i.test(hash)) throw new Error("Provide the actual registration transaction hash from MetaMask Activity.");
    if (wait) await rpc.waitForTransactionReceipt({ hash: hash as Hex, timeout: 20_000, pollingInterval: 1500 });
    const verified = await verifyRegistration(rpc, hash as Hex);
    setProof(verified); onRegistered(verified);
    setNotice("ERC-8004 registration independently verified on Fuji: Registered event, agent ID, owner and tokenURI match.");
  }
  async function register() {
    await guarded(async () => {
      if (!provider.current) throw new Error("Open this page in Opera with MetaMask unlocked. A private key is not required here.");
      if (!navigator.locks) throw new Error("Browser transaction locking unavailable; signing disabled.");
      const next = await preflight(); setPlan(next);
      if (next.registered) { setProof(next.registered); onRegistered(next.registered); return; }
      if (next.owned_identity_count !== "0") throw new Error("Existing identity found; verify the prior registration instead of minting again.");
      setNotice("Approve access to the expected test account and Fuji network in MetaMask if requested.");
      await connectFuji(provider.current);
      const wallet = provider.current;
      try {
        setNotice("Review register(agentURI) in MetaMask. Zero AVAX transfer; maximum configured gas fee 0.0125 test AVAX.");
        const submitted = await navigator.locks.request("aegis-fuji-wallet-signing", async () => {
          await assertUnregistered(rpc);
          return sendFujiTransaction(wallet, registrationTransaction(), localStorage);
        });
        setOperation(submitted);
        try { await check(submitted.hash!, true); }
        catch { setNotice("Registration hash received but confirmation is not yet verified. Recheck the transaction; do not mint again."); }
      } catch (error) {
        setOperation(loadOperation(localStorage, registrationTransaction())); throw error;
      }
    });
  }
  const blocked = operation && operation.status !== "REJECTED";
  const button = "rounded-lg border border-[#4EE1C2]/40 bg-[#4EE1C2]/10 px-4 py-2 text-sm font-semibold text-[#4EE1C2] disabled:opacity-40";
  return (
    <section aria-label="ERC-8004 MetaMask registration" className="aegis-card space-y-3 rounded-2xl border border-[#4EE1C2]/30 p-5">
      <h2 className="text-lg font-semibold">ERC-8004 · Register AEGIS on Fuji</h2>
      <p className="break-all text-xs text-[#9BA7B4]">Owner: {EXPECTED_FUJI_ACCOUNT}<br />Official registry: {IDENTITY_REGISTRY}<br />Metadata: <a className="text-[#4EE1C2] underline" href={AGENT_METADATA_URI} target="_blank" rel="noreferrer">Public agent-registration.json</a></p>
      <p className="text-xs text-[#9BA7B4]">One agent identity NFT; AVAX transfer value 0. Configured gas ceiling 0.0125 test AVAX before any wallet edits. This does not activate a public API or authorize exchange trading.</p>
      <p role="status" className="text-sm text-[#9BA7B4]">{notice}</p>
      <button className={button} disabled={!plan || plan.owned_identity_count !== "0" || busy || Boolean(blocked) || Boolean(proof)} onClick={register}>3. Register ERC-8004 identity</button>
      {operation && <p className="text-xs">Registration request: {operation.status}</p>}
      {operation?.hash && <a className="block break-all text-xs text-[#4EE1C2] underline" target="_blank" rel="noreferrer" href={`https://testnet.snowtrace.io/tx/${operation.hash}`}>{operation.hash}</a>}
      {proof && <p className="break-all text-sm text-[#4EE1C2]">VERIFIED · Agent #{proof.agentId} · Owner {proof.owner} · Block {proof.blockNumber} · Actual fee {formatEther(BigInt(proof.fee_wei))} test AVAX</p>}
      <div className="flex flex-wrap items-center gap-2">
        <input aria-label="Registration recovery transaction hash" className="min-w-60 flex-1 rounded-lg border border-[#2A3542] bg-[#0A0D10] px-3 py-2 font-mono text-xs" placeholder="Actual registration transaction hash (optional recovery)" value={recoveryHash} onChange={event => setRecoveryHash(event.target.value)} />
        <button className={button} disabled={busy || !(operation?.hash || recoveryHash)} onClick={() => guarded(() => check(recoveryHash || operation?.hash || ""))}>Recheck registration</button>
      </div>
    </section>
  );
}
