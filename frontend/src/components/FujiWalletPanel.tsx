"use client";

import React from "react";
import { createPublicClient, formatEther, http, type Address } from "viem";
import { avalancheFuji } from "viem/chains";
import { discoverMetaMask } from "@/lib/metamask-provider";
import {
  connectFuji, deploymentTransaction, EXPECTED_FUJI_ACCOUNT, FUJI_RPC,
  loadOperation, receiptTransaction, sendFujiTransaction, verifyFujiTransaction,
  type FujiPlan, type FujiProof, type Operation, type WalletProvider,
} from "@/lib/fuji-wallet";

const rpc = createPublicClient({ chain: avalancheFuji, transport: http(FUJI_RPC, { timeout: 8000, retryCount: 0 }) });
const message = (error: unknown) => error instanceof Error ? error.message : "Wallet operation unavailable. No automatic retry.";

function download(name: string, data: unknown) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
  const link = document.createElement("a"); link.href = url; link.download = name; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function FujiWalletPanel({ onVerified }: { onVerified: (registry: Address, digest: string) => void }) {
  const [plan, setPlan] = React.useState<FujiPlan | null>(null);
  const [connected, setConnected] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const lock = React.useRef(false);
  const metamask = React.useRef<WalletProvider | undefined>(undefined);
  const [notice, setNotice] = React.useState("Connect your funded MetaMask test account. Connecting does not submit a transaction.");
  const [planError, setPlanError] = React.useState("");
  const [deploy, setDeploy] = React.useState<Operation | null>(null);
  const [record, setRecord] = React.useState<Operation | null>(null);
  const [deployProof, setDeployProof] = React.useState<FujiProof | null>(null);
  const [recordProof, setRecordProof] = React.useState<FujiProof | null>(null);

  React.useEffect(() => {
    let active = true;
    fetch("/api/web3/deployment-plan", { cache: "no-store" })
      .then(async response => {
        if (!response.ok) throw new Error("Verified deployment plan unavailable; signing disabled.");
        const next: FujiPlan = await response.json();
        const tx = deploymentTransaction(next);
        if (active) { setPlan(next); setDeploy(loadOperation(localStorage, tx)); }
      })
      .catch(error => { if (active) setPlanError(message(error)); });
    const changed = () => { setConnected(false); setNotice("Wallet account or network changed. Reconnect and verify Fuji before signing."); };
    const providers = new Set<WalletProvider>();
    const discovery = discoverMetaMask(window, provider => {
      metamask.current = provider; providers.add(provider);
      provider.on?.("accountsChanged", changed); provider.on?.("chainChanged", changed);
    });
    return () => {
      active = false; discovery.stop(); metamask.current = undefined;
      for (const provider of providers) { provider.removeListener?.("accountsChanged", changed); provider.removeListener?.("chainChanged", changed); }
    };
  }, []);

  async function guarded(work: () => Promise<void>) {
    if (lock.current) return;
    lock.current = true; setBusy(true);
    try { await work(); } catch (error) { setNotice(message(error)); }
    finally { lock.current = false; setBusy(false); }
  }
  async function connect() {
    await guarded(async () => {
      setNotice("Approve account access in MetaMask, then approve switching to Fuji if requested. No transaction is being sent.");
      await connectFuji(metamask.current); setConnected(true);
      setNotice("MetaMask connected to the expected account on Fuji 43113. No transaction submitted.");
    });
  }
  async function check(kind: "deploy" | "record", operation: Operation | null, wait = false) {
    if (!plan || !operation?.hash) throw new Error("No transaction hash is available. Inspect MetaMask Activity; an uncertain request must not be resubmitted.");
    if (wait) await rpc.waitForTransactionReceipt({ hash: operation.hash, timeout: 20_000, pollingInterval: 1500 });
    const proof = await verifyFujiTransaction(rpc, plan, kind, operation.hash, deployProof?.contract_address);
    if (kind === "deploy") {
      setDeployProof(proof);
      setRecord(loadOperation(localStorage, receiptTransaction(plan, proof.contract_address)));
      setNotice("Deployment independently verified on Fuji: runtime bytecode and owner match. Recording the HALT digest requires a separate approval.");
    } else {
      setRecordProof(proof); onVerified(proof.contract_address, plan.decision_hash);
      setNotice("HALT receipt independently verified on Fuji: digest, run, policy tag, caller and verdict match. Identity registration is verified separately.");
    }
  }
  async function submit(kind: "deploy" | "record") {
    await guarded(async () => {
      if (!plan || !connected) throw new Error("Connect MetaMask on Fuji first.");
      const provider = metamask.current;
      if (!provider) throw new Error("MetaMask extension is unavailable.");
      if (!navigator.locks) throw new Error("Browser transaction locking unavailable; signing disabled.");
      const tx = kind === "deploy" ? deploymentTransaction(plan) : receiptTransaction(plan, deployProof?.contract_address ?? "");
      try {
        setNotice("Review this Fuji transaction in MetaMask. Only this selected step will be submitted.");
        const operation = await navigator.locks.request("aegis-fuji-wallet-signing", () => sendFujiTransaction(provider, tx, localStorage));
        if (kind === "deploy") setDeploy(operation); else setRecord(operation);
        setNotice("Transaction hash received; waiting for confirmation and independent read-back. Do not resubmit.");
        try { await check(kind, operation, true); }
        catch { setNotice("Submitted but not independently verified yet. Use Recheck transaction; do not send it again."); }
      } catch (error) {
        const saved = loadOperation(localStorage, tx);
        if (kind === "deploy") setDeploy(saved); else setRecord(saved);
        throw error;
      }
    });
  }
  const blocked = (operation: Operation | null) => Boolean(operation && operation.status !== "REJECTED");
  const button = "rounded-lg border border-[#4EE1C2]/40 bg-[#4EE1C2]/10 px-4 py-2 text-sm font-semibold text-[#4EE1C2] disabled:opacity-40";

  return (
    <section aria-label="MetaMask Fuji signing" className="aegis-card space-y-4 rounded-2xl border border-[#4EE1C2]/30 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><h2 className="text-lg font-semibold">MetaMask · Fuji testnet signing</h2><p className="text-xs text-[#9BA7B4]">Separate wallet approvals for deployment and audit receipt. Private keys stay in MetaMask.</p></div>
        <button className={button} disabled={busy} onClick={connect}>Connect MetaMask</button>
      </div>
      <p className="break-all font-mono text-xs">Expected funded account: {EXPECTED_FUJI_ACCOUNT}</p>
      <p role="status" className="text-sm text-[#9BA7B4]">{notice}</p>
      {planError && <p role="alert" className="text-sm text-amber-300">{planError}</p>}
      <div className="grid gap-3 text-xs text-[#9BA7B4] sm:grid-cols-2">
        <p>Network: Avalanche Fuji · 43113<br />AVAX transfer value: 0<br />Deploy fee ceiling: 0.025 test AVAX<br />Record fee ceiling: 0.00625 test AVAX</p>
        <p className="break-all">Recorded backend HALT sample; not a fresh trading signal.<br />SHA-256: {plan?.decision_hash ?? "Loading verified plan…"}<br />ERC-8004 identity has a separate registration and verification panel below.</p>
      </div>
      <div className="flex flex-wrap gap-3">
        <button className={button} disabled={!plan || !connected || busy || blocked(deploy)} onClick={() => submit("deploy")}>1. Deploy receipt contract</button>
        <button className={button} disabled={!deployProof || !connected || busy || blocked(record)} onClick={() => submit("record")}>2. Record HALT receipt</button>
        {plan && <button className={button} onClick={() => download("aegis-fuji-unsigned-plan.json", plan)}>Review unsigned plan</button>}
      </div>
      {([ ["deploy", deploy, deployProof], ["record", record, recordProof] ] as const).map(([kind, operation, proof]) => operation && (
        <div key={kind} className="space-y-2 rounded-lg border border-[#2A3542] p-3 text-xs">
          <p>{kind === "deploy" ? "Deployment" : "HALT receipt"}: <strong>{proof ? "VERIFIED ON FUJI" : operation.status}</strong></p>
          {operation.hash && <a className="break-all text-[#4EE1C2] underline" target="_blank" rel="noreferrer" href={`https://testnet.snowtrace.io/tx/${operation.hash}`}>{operation.hash}</a>}
          {proof && <p className="break-all">Contract: {proof.contract_address} · Block: {proof.block_number} · Actual fee: {formatEther(BigInt(proof.fee_wei))} test AVAX</p>}
          <div className="flex flex-wrap gap-3">
            {operation.hash && <button className={button} disabled={busy || (kind === "record" && !deployProof)} onClick={() => guarded(() => check(kind, operation))}>Recheck {kind} transaction</button>}
            {proof && <button className={button} onClick={() => download(`aegis-fuji-${kind}-proof.json`, { ...proof, operation, plan })}>Download {kind} proof</button>}
          </div>
        </div>
      ))}
      <p className="text-xs text-[#9BA7B4]">Use the browser where MetaMask is installed (for example Chrome). Codex’s in-app browser may not expose the extension. Signing never enables exchange execution.</p>
    </section>
  );
}
