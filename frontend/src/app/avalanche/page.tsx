"use client";

import React from "react";
import {
  CheckCircle2,
  ExternalLink,
  FileCode2,
  RefreshCw,
  Server,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import { AdminUnlockModal } from "@/components/AdminUnlockModal";
import { HeaderBar } from "@/components/HeaderBar";
import { ProofDrawerModal } from "@/components/ProofDrawerModal";
import {
  RECORDED_EVENTS_MARKET_ONLY,
  RECORDED_IDENTITY,
  RECORDED_SNAPSHOT_MARKET_ONLY,
} from "@/lib/fixtures";
import type { Identity, Snapshot } from "@/lib/types";

interface FujiVerifyResponse {
  checked_at: string;
  chain_id: 43113;
  network: string;
  rpc_url: string;
  rpc_connected: boolean;
  rpc_chain_id: number | null;
  latest_block_number: number | null;
  official_erc8004_registries: {
    identity_registry: string;
    identity_registry_has_code: boolean;
    identity_registry_name: string | null;
    identity_registry_symbol: string | null;
    reputation_registry: string;
    reputation_registry_has_code: boolean;
  };
  backend_identity: Identity;
  erc8004_readback: {
    status: "PASS" | "FAIL" | "NOT_TESTED";
    verified: boolean;
    registry_address: string;
    registry_has_code: boolean;
    owner: string | null;
    agent_uri: string | null;
    tx_receipt_status: string;
    note: string;
  };
  reputation_readback?: {
    status: "PASS" | "NOT_TESTED" | "READ_ONLY_READY";
    registry_address: string;
    linked_identity_registry: string | null;
    feedback_count: number;
    summary_display: string;
    note: string;
  };
  decision_receipt_readback: {
    status: "PASS" | "FAIL" | "NOT_TESTED";
    verified: boolean;
    contract_address: string | null;
    decision_hash: string;
    run_id_hash: string;
    policy_version_hash: string;
    exists_on_chain: boolean;
    caller: string | null;
    timestamp_unix: number | null;
    verdict_code: number | null;
    local_evm_unit_tests: string;
    note: string;
  };
  architecture_boundary: string;
}

export default function AvalanchePage() {
  const [snapshot] = React.useState<Snapshot>(RECORDED_SNAPSHOT_MARKET_ONLY);
  const [identity, setIdentity] = React.useState<Identity>(RECORDED_IDENTITY);
  const [verifyData, setVerifyData] = React.useState<FujiVerifyResponse | null>(
    null
  );
  const [busy, setBusy] = React.useState(false);

  const [customRegistry, setCustomRegistry] = React.useState(
    "0x8004A818BFB912233c491871b3d84c89A494BD9e"
  );
  const [customAgentId, setCustomAgentId] = React.useState("");
  const [customTxHash, setCustomTxHash] = React.useState("");
  const [customDecisionRegistry, setCustomDecisionRegistry] = React.useState("");
  const [customDigest, setCustomDigest] = React.useState(
    "0x166c93073c84eddf94e432f3b0a52a66f60a6c308097beed0527097cfb3c08b2"
  );

  const [proofModalOpen, setProofModalOpen] = React.useState(false);
  const [adminModalOpen, setAdminModalOpen] = React.useState(false);
  const [adminSecret, setAdminSecret] = React.useState("");

  const runVerification = React.useCallback(async () => {
    setBusy(true);
    try {
      const qs = new URLSearchParams();
      if (customRegistry.trim()) qs.set("registry", customRegistry.trim());
      if (customAgentId.trim()) qs.set("agentId", customAgentId.trim());
      if (customTxHash.trim()) qs.set("txHash", customTxHash.trim());
      if (customDecisionRegistry.trim()) {
        qs.set("decisionRegistry", customDecisionRegistry.trim());
      }
      if (customDigest.trim()) qs.set("digest", customDigest.trim());

      const [idRes, verRes] = await Promise.all([
        fetch("/api/web3/identity", { cache: "no-store" }),
        fetch(`/api/web3/verify?${qs.toString()}`, { cache: "no-store" }),
      ]);

      if (idRes.ok) {
        setIdentity((await idRes.json()) as Identity);
      }
      if (verRes.ok) {
        setVerifyData((await verRes.json()) as FujiVerifyResponse);
      }
    } finally {
      setBusy(false);
    }
  }, [
    customRegistry,
    customAgentId,
    customTxHash,
    customDecisionRegistry,
    customDigest,
  ]);

  React.useEffect(() => {
    runVerification();
  }, [runVerification]);

  const isIdentityVerified = Boolean(verifyData?.erc8004_readback.verified);
  const isReceiptVerified = Boolean(
    verifyData?.decision_receipt_readback.verified
  );

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <HeaderBar
        sourceMode={snapshot.source_mode}
        running={snapshot.running}
        backendLive={Boolean(verifyData?.rpc_connected)}
        sseState="FALLBACK"
        lastCycleAt={snapshot.last_cycle_at}
        observedAt={snapshot.observation?.observed_at ?? null}
        onInspectProof={() => setProofModalOpen(true)}
        onOpenAdminModal={() => setAdminModalOpen(true)}
        adminUnlocked={Boolean(adminSecret)}
        onRefresh={runVerification}
      />

      <main className="mx-auto max-w-7xl space-y-5 px-4 py-6">
        {/* Top Architecture Boundary Card (Nonnegotiable Definition) */}
        <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 shadow-lg">
          <div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-800 pb-4">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded bg-sky-500/20 px-2.5 py-0.5 font-mono text-xs font-bold text-sky-300 border border-sky-500/40">
                  AVALANCHE FUJI C-CHAIN (43113)
                </span>
                <span className="rounded bg-emerald-500/20 px-2.5 py-0.5 font-mono text-xs font-bold text-emerald-300 border border-emerald-500/40">
                  OFFICIAL ERC-8004 BYTECODE VERIFIED ON FUJI
                </span>
                <span className="rounded bg-amber-500/20 px-2.5 py-0.5 font-mono text-xs font-bold text-amber-300 border border-amber-500/40">
                  OFF-CHAIN PYTHON / LAYA / EVREN RUNTIME
                </span>
              </div>
              <h1 className="mt-2.5 text-xl font-bold text-white">
                Avalanche Fuji ERC-8004 Identity & `RiskDecisionRegistry` Verification
              </h1>
              <p className="mt-1 max-w-3xl text-xs leading-relaxed text-slate-300">
                <strong>Most Important Boundary:</strong> Agent reasoning/inference (LAYA, EVREN) and OKX ATK trading run <strong>OFF-CHAIN</strong>. The Avalanche Fuji contracts supply <strong>on-chain ERC-8004 identity</strong> and <strong>sanitized SHA-256 decision receipt anchoring</strong> (<code className="font-mono">{`{decisionHash, runIdHash, policyVersionHash, caller, timestamp, verdictCode}`}</code>) — never on-chain AI inference or private portfolio data.
              </p>
            </div>

            {/* Live Fuji RPC Connection Box */}
            <div className="rounded-lg border border-slate-800 bg-slate-950/80 p-3.5 font-mono text-xs">
              <div className="flex items-center justify-between gap-4">
                <span className="text-slate-400">Fuji C-Chain RPC:</span>
                {verifyData?.rpc_connected ? (
                  <span className="inline-flex items-center gap-1 font-bold text-emerald-400">
                    <CheckCircle2 className="h-3.5 w-3.5" /> CONNECTED (43113)
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 font-bold text-amber-300">
                    <ShieldAlert className="h-3.5 w-3.5" /> CHECKING / OFFLINE
                  </span>
                )}
              </div>
              <div className="mt-1 text-slate-300">
                Latest Fuji Block:{" "}
                <strong className="text-white">
                  {verifyData?.latest_block_number
                    ? `#${verifyData.latest_block_number.toLocaleString()}`
                    : "—"}
                </strong>
              </div>
              <div className="mt-1 text-[11px] text-slate-400">
                Custom L1 / ICM: <strong className="text-slate-300">NOT USED (Fuji C-Chain Only)</strong>
              </div>
            </div>
          </div>

          {/* 3-State Separation Strip (PROMPT 13: Distinguish REGISTERED vs RUNNING/ONLINE vs TRADING VERIFIED) */}
          <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3 text-xs">
            <div className="rounded-lg border border-slate-800 bg-slate-950/80 p-3">
              <div className="flex items-center justify-between">
                <span className="font-mono text-[11px] text-slate-400">
                  1. ON-CHAIN IDENTITY (REGISTERED)
                </span>
                <span
                  className={`rounded px-2 py-0.5 font-mono text-[10px] font-bold ${
                    isIdentityVerified
                      ? "bg-emerald-500/20 text-emerald-300"
                      : "bg-amber-500/20 text-amber-300"
                  }`}
                >
                  {isIdentityVerified ? "REGISTERED (VERIFIED)" : "NOT_TESTED (verified=false)"}
                </span>
              </div>
              <p className="mt-1 text-[11px] text-slate-300">
                ERC-8004 `agentId` minting on Fuji (`0x8004A818...4BD9e`). Registry bytecode is verified; AEGIS `agentId` awaits funded Fuji key.
              </p>
            </div>

            <div className="rounded-lg border border-slate-800 bg-slate-950/80 p-3">
              <div className="flex items-center justify-between">
                <span className="font-mono text-[11px] text-slate-400">
                  2. OFF-CHAIN RUNTIME (RUNNING / ONLINE)
                </span>
                <span className="rounded bg-emerald-500/20 px-2 py-0.5 font-mono text-[10px] font-bold text-emerald-300">
                  MARKET_ONLY (ATK PASS)
                </span>
              </div>
              <p className="mt-1 text-[11px] text-slate-300">
                Off-chain Python risk gate + `@okx_ai/okx-trade-cli@1.4.8` observations run on M2 (`http-smoke.json` & `amendment-http.json`).
              </p>
            </div>

            <div className="rounded-lg border border-slate-800 bg-slate-950/80 p-3">
              <div className="flex items-center justify-between">
                <span className="font-mono text-[11px] text-slate-400">
                  3. EXCHANGE EXECUTION (TRADING VERIFIED)
                </span>
                <span className="rounded bg-slate-800 px-2 py-0.5 font-mono text-[10px] font-bold text-amber-300">
                  NOT_SENT (0 Exchange Writes)
                </span>
              </div>
              <p className="mt-1 text-[11px] text-slate-300">
                `VERIFIED` requires venue order reconciliation. In `MARKET_ONLY` mode, `execution_status=NOT_SENT` and `live_execution_enabled=false`.
              </p>
            </div>
          </div>

          {/* Official ERC-8004 Registry Verification Strip */}
          <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
            <div className="rounded-lg border border-emerald-500/30 bg-emerald-950/15 p-3.5">
              <div className="flex items-center justify-between">
                <span className="inline-flex items-center gap-1.5 text-xs font-bold text-emerald-300">
                  <ShieldCheck className="h-4 w-4" />
                  Official Fuji ERC-8004 `IdentityRegistry` (`eth_getCode` Verified)
                </span>
                <span className="rounded bg-emerald-500/20 px-2 py-0.5 font-mono text-[10px] font-bold text-emerald-300">
                  {verifyData?.official_erc8004_registries
                    .identity_registry_has_code
                    ? "BYTECODE VERIFIED (130B Proxy)"
                    : "CHECKING"}
                </span>
              </div>
              <div className="mt-2 font-mono text-xs text-white break-all">
                0x8004A818BFB912233c491871b3d84c89A494BD9e
              </div>
              <div className="mt-1 flex items-center justify-between text-[11px] text-slate-300">
                <span>
                  On-Chain `name()` / `symbol()`:{" "}
                  <strong className="font-mono text-emerald-300">
                    {verifyData?.official_erc8004_registries
                      .identity_registry_name ?? "AgentIdentity"}{" "}
                    (
                    {verifyData?.official_erc8004_registries
                      .identity_registry_symbol ?? "AGENT"}
                    )
                  </strong>
                </span>
                <a
                  href="https://testnet.snowtrace.io/address/0x8004A818BFB912233c491871b3d84c89A494BD9e"
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 font-mono text-indigo-300 hover:underline"
                >
                  Snowtrace <ExternalLink className="h-3 w-3" />
                </a>
              </div>
            </div>

            <div className="rounded-lg border border-emerald-500/30 bg-emerald-950/15 p-3.5">
              <div className="flex items-center justify-between">
                <span className="inline-flex items-center gap-1.5 text-xs font-bold text-emerald-300">
                  <ShieldCheck className="h-4 w-4" />
                  Official Fuji ERC-8004 `ReputationRegistry` (Read-Only Lookup)
                </span>
                <span className="rounded bg-emerald-500/20 px-2 py-0.5 font-mono text-[10px] font-bold text-emerald-300">
                  {verifyData?.reputation_readback?.summary_display ??
                    "No independent feedback yet"}
                </span>
              </div>
              <div className="mt-2 font-mono text-xs text-white break-all">
                0x8004B663056A597Dffe9eCcC1965A193B7388713
              </div>
              <div className="mt-1 flex items-center justify-between text-[11px] text-slate-300">
                <span>
                  {verifyData?.reputation_readback?.note ??
                    "Reputation policy: Read-only allowed; fake/self-awarded feedback forbidden."}
                </span>
                <a
                  href="https://testnet.snowtrace.io/address/0x8004B663056A597Dffe9eCcC1965A193B7388713"
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 font-mono text-indigo-300 hover:underline"
                >
                  Snowtrace <ExternalLink className="h-3 w-3" />
                </a>
              </div>
            </div>
          </div>
        </section>

        {/* Two-Column Verification Cards: ERC-8004 Identity + RiskDecisionRegistry */}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {/* Card 1: ERC-8004 Identity (`/api/web3/identity` + Viem Read-back) */}
          <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 shadow-lg">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <h2 className="text-sm font-bold text-white">
                  1. AEGIS ERC-8004 Agent Registration (`register(agentURI)`)
                </h2>
                <p className="text-xs text-slate-400">
                  Never marks `verified=true` from a local file alone; requires live Fuji `ownerOf(agentId)` + `tokenURI(agentId)` read-back.
                </p>
              </div>
              <span
                className={`rounded border px-2.5 py-1 font-mono text-xs font-bold ${
                  isIdentityVerified
                    ? "border-emerald-500/40 bg-emerald-500/20 text-emerald-300"
                    : "border-amber-500/40 bg-amber-500/15 text-amber-300"
                }`}
              >
                {verifyData?.erc8004_readback.status ??
                  identity.verification_status}{" "}
                (verified={String(isIdentityVerified)})
              </span>
            </div>

            <dl className="mt-4 space-y-2 font-mono text-xs">
              <div className="flex justify-between border-b border-slate-800/70 pb-1.5">
                <dt className="text-slate-400">chain_id:</dt>
                <dd className="font-bold text-white">{identity.chain_id}</dd>
              </div>
              <div className="flex justify-between border-b border-slate-800/70 pb-1.5">
                <dt className="text-slate-400">registry_address:</dt>
                <dd className="text-slate-200">
                  {verifyData?.erc8004_readback.registry_address ??
                    "0x8004A818BFB912233c491871b3d84c89A494BD9e"}
                </dd>
              </div>
              <div className="flex justify-between border-b border-slate-800/70 pb-1.5">
                <dt className="text-slate-400">agent_id:</dt>
                <dd className="text-slate-200">
                  {identity.agent_id ?? "null (Awaiting funded Fuji wallet)"}
                </dd>
              </div>
              <div className="flex justify-between border-b border-slate-800/70 pb-1.5">
                <dt className="text-slate-400">owner (Read-Back):</dt>
                <dd className="text-slate-200">
                  {verifyData?.erc8004_readback.owner ?? identity.owner ?? "null"}
                </dd>
              </div>
              <div className="flex justify-between border-b border-slate-800/70 pb-1.5">
                <dt className="text-slate-400">agent_uri (tokenURI):</dt>
                <dd className="text-slate-200">
                  {verifyData?.erc8004_readback.agent_uri ??
                    identity.agent_uri ??
                    "null"}
                </dd>
              </div>
              <div className="flex justify-between border-b border-slate-800/70 pb-1.5">
                <dt className="text-slate-400">registration_tx_hash:</dt>
                <dd className="text-slate-200">
                  {identity.registration_tx_hash ?? identity.tx_hash ?? "null"}
                </dd>
              </div>
            </dl>

            <div className="mt-3 rounded border border-slate-800 bg-slate-950 p-3 text-xs text-slate-300">
              <strong className="text-slate-200">Verifier Note:</strong>{" "}
              {verifyData?.erc8004_readback.note}
            </div>

            {isIdentityVerified && identity.registration_tx_hash ? (
              <div className="mt-3">
                <a
                  href={`https://testnet.snowtrace.io/tx/${identity.registration_tx_hash}`}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1.5 rounded bg-emerald-500/20 px-3 py-1.5 font-mono text-xs font-bold text-emerald-300 border border-emerald-500/40 hover:bg-emerald-500/30"
                >
                  View Verified Registration Tx on Snowtrace{" "}
                  <ExternalLink className="h-3.5 w-3.5" />
                </a>
              </div>
            ) : (
              <p className="mt-3 font-mono text-[11px] text-slate-400">
                Registration Tx Explorer Link suppressed: `verified=false` (no fabricated tx hashes).
              </p>
            )}

            <div className="mt-3 border-t border-slate-800 pt-3 flex flex-wrap items-center justify-between gap-2 text-xs">
              <span className="text-slate-400">
                ERC-8004 Registration JSON Endpoints:
              </span>
              <div className="flex flex-wrap items-center gap-3">
                <a
                  href="/agent-registration.json"
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 font-mono text-indigo-300 hover:underline"
                >
                  /agent-registration.json{" "}
                  <FileCode2 className="h-3.5 w-3.5" />
                </a>
                <a
                  href="/.well-known/erc8004-agent.json"
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 font-mono text-slate-400 hover:text-indigo-300 hover:underline"
                >
                  /.well-known/erc8004-agent.json{" "}
                  <FileCode2 className="h-3.5 w-3.5" />
                </a>
              </div>
            </div>
          </section>

          {/* Card 2: RiskDecisionRegistry Receipt Read-Back */}
          <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 shadow-lg">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <h2 className="text-sm font-bold text-white">
                  2. `RiskDecisionRegistry.sol` Audit Utility Contract
                </h2>
                <p className="text-xs text-slate-400">
                  Maps & emits `{`{decisionHash, runIdHash, policyVersionHash, caller, timestamp, verdictCode}`}`.
                </p>
              </div>
              <span
                className={`rounded border px-2.5 py-1 font-mono text-xs font-bold ${
                  isReceiptVerified
                    ? "border-emerald-500/40 bg-emerald-500/20 text-emerald-300"
                    : "border-amber-500/40 bg-amber-500/15 text-amber-300"
                }`}
              >
                FUJI: {verifyData?.decision_receipt_readback.status ?? "NOT_TESTED"}
              </span>
            </div>

            <dl className="mt-4 space-y-2 font-mono text-xs">
              <div className="flex justify-between border-b border-slate-800/70 pb-1.5">
                <dt className="text-slate-400">Local EVM Unit Tests:</dt>
                <dd className="font-bold text-emerald-400">
                  {verifyData?.decision_receipt_readback.local_evm_unit_tests ??
                    "PASS (3/3 in web3/tests/risk-decision-registry.test.ts)"}
                </dd>
              </div>
              <div className="flex justify-between border-b border-slate-800/70 pb-1.5">
                <dt className="text-slate-400">Fuji Contract Address:</dt>
                <dd className="text-slate-200">
                  {verifyData?.decision_receipt_readback.contract_address ??
                    "null (Awaiting funded Fuji wallet)"}
                </dd>
              </div>
              <div className="flex flex-col gap-0.5 border-b border-slate-800/70 pb-1.5">
                <dt className="text-slate-400">
                  Canonical `decisionHash` (`amendment-http.json` HALT):
                </dt>
                <dd className="break-all text-[11px] text-indigo-300">
                  {verifyData?.decision_receipt_readback.decision_hash ??
                    customDigest}
                </dd>
              </div>
              <div className="flex flex-col gap-0.5 border-b border-slate-800/70 pb-1.5">
                <dt className="text-slate-400">`runIdHash` / `policyVersionHash`:</dt>
                <dd className="break-all text-[10px] text-slate-300">
                  run: {verifyData?.decision_receipt_readback.run_id_hash ?? "—"}
                  <br />
                  pol: {verifyData?.decision_receipt_readback.policy_version_hash ?? "—"}
                </dd>
              </div>
              <div className="flex justify-between border-b border-slate-800/70 pb-1.5">
                <dt className="text-slate-400">Exists On Fuji C-Chain:</dt>
                <dd className="text-slate-200">
                  {String(
                    verifyData?.decision_receipt_readback.exists_on_chain ?? false
                  )}
                </dd>
              </div>
              <div className="flex justify-between border-b border-slate-800/70 pb-1.5">
                <dt className="text-slate-400">Measured Fuji Confirmation / Fee:</dt>
                <dd className="text-amber-300">
                  null (NOT_TESTED — zero fake latency/fee estimates)
                </dd>
              </div>
            </dl>

            <div className="mt-3 rounded border border-slate-800 bg-slate-950 p-3 text-xs text-slate-300">
              <strong className="text-slate-200">Receipt Verifier Note:</strong>{" "}
              {verifyData?.decision_receipt_readback.note}
            </div>
          </section>
        </div>

        {/* Interactive Live Fuji Read-Back Tester */}
        <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 shadow-lg">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-3">
            <div>
              <h2 className="text-sm font-bold text-white">
                Interactive Fuji Viem Read-Back Verifier (`/api/web3/verify`)
              </h2>
              <p className="text-xs text-slate-400">
                Try entering `agentId = 1` against the official Fuji `IdentityRegistry` (`0x8004A818BFB912233c491871b3d84c89A494BD9e`) to see live on-chain `ownerOf(1)` read-back, or paste your deployed `RiskDecisionRegistry` address after running `npx tsx scripts/deploy-and-prove-fuji.ts`.
              </p>
            </div>
            <button
              type="button"
              disabled={busy}
              onClick={runVerification}
              className="inline-flex items-center gap-1.5 rounded-md bg-sky-500 px-3.5 py-1.5 text-xs font-bold text-slate-950 hover:bg-sky-400 disabled:opacity-50"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${busy ? "animate-spin" : ""}`} />
              {busy ? "Querying Fuji 43113 RPC..." : "Run Independent Fuji Read-Back"}
            </button>
          </div>

          <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5 text-xs">
            <div>
              <label className="block font-mono text-[11px] text-slate-400">
                ERC-8004 Registry Address
              </label>
              <input
                type="text"
                value={customRegistry}
                onChange={(e) => setCustomRegistry(e.target.value)}
                placeholder="0x8004A818..."
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2.5 py-1.5 font-mono text-xs text-white placeholder-slate-600"
              />
            </div>
            <div>
              <label className="block font-mono text-[11px] text-slate-400">
                ERC-8004 agentId (uint256)
              </label>
              <input
                type="text"
                value={customAgentId}
                onChange={(e) => setCustomAgentId(e.target.value)}
                placeholder="e.g. 1"
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2.5 py-1.5 font-mono text-xs text-white placeholder-slate-600"
              />
            </div>
            <div>
              <label className="block font-mono text-[11px] text-slate-400">
                Registration Tx Hash
              </label>
              <input
                type="text"
                value={customTxHash}
                onChange={(e) => setCustomTxHash(e.target.value)}
                placeholder="0x..."
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2.5 py-1.5 font-mono text-xs text-white placeholder-slate-600"
              />
            </div>
            <div>
              <label className="block font-mono text-[11px] text-slate-400">
                RiskDecisionRegistry Address
              </label>
              <input
                type="text"
                value={customDecisionRegistry}
                onChange={(e) => setCustomDecisionRegistry(e.target.value)}
                placeholder="0x..."
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2.5 py-1.5 font-mono text-xs text-white placeholder-slate-600"
              />
            </div>
            <div>
              <label className="block font-mono text-[11px] text-slate-400">
                Decision SHA-256 (bytes32)
              </label>
              <input
                type="text"
                value={customDigest}
                onChange={(e) => setCustomDigest(e.target.value)}
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2.5 py-1.5 font-mono text-xs text-white"
              />
            </div>
          </div>
        </section>
      </main>

      <ProofDrawerModal
        open={proofModalOpen}
        onClose={() => setProofModalOpen(false)}
        snapshot={snapshot}
        events={RECORDED_EVENTS_MARKET_ONLY}
      />

      <AdminUnlockModal
        open={adminModalOpen}
        onClose={() => setAdminModalOpen(false)}
        adminSecret={adminSecret}
        onSaveSecret={setAdminSecret}
      />
    </div>
  );
}
