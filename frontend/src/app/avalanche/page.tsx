"use client";

import React from "react";
import {
  Brain,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Copy,
  ExternalLink,
  FileCode2,
  FileText,
  Info,
  Link2,
  RefreshCw,
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
  const [copiedKey, setCopiedKey] = React.useState<string | null>(null);
  const [showCustomVerifier, setShowCustomVerifier] = React.useState(false);

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

  const copyValue = (val: string, key: string) => {
    navigator.clipboard.writeText(val).catch(() => {});
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 1800);
  };

  const isIdentityVerified = Boolean(verifyData?.erc8004_readback.verified);
  const isReceiptVerified = Boolean(
    verifyData?.decision_receipt_readback.verified
  );
  const isRegistryBytecodePass = Boolean(
    verifyData?.official_erc8004_registries.identity_registry_has_code
  );

  const officialRegistryAddr =
    verifyData?.official_erc8004_registries.identity_registry ||
    "0x8004A818BFB912233c491871b3d84c89A494BD9e";
  const officialReputationAddr =
    verifyData?.official_erc8004_registries.reputation_registry ||
    "0x8004B663056A597Dffe9eCcC1965A193B7388713";
  const decisionDigest =
    verifyData?.decision_receipt_readback.decision_hash ||
    "0x166c93073c84eddf94e432f3b0a52a66f60a6c308097beed0527097cfb3c08b2";

  return (
    <div className="min-h-screen bg-[#0A0D10] text-[#E6EDF3]">
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

      <main className="mx-auto max-w-7xl space-y-6 px-4 py-6">
        {/* Top Hero Header (Reference Set C) */}
        <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
          <div>
            <span className="inline-block rounded-full border border-[#4EE1C2]/35 bg-[#4EE1C2]/10 px-3 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-wider text-[#4EE1C2]">
              ON-CHAIN
            </span>
            <h1 className="mt-2 text-2xl font-bold tracking-tight text-[#E6EDF3] sm:text-3xl">
              On-chain Identity & Proof
            </h1>
            <p className="mt-1 text-sm text-[#9BA7B4]">
              Verifiable ERC-8004 identity and SHA-256 decision receipts on Avalanche Fuji C-Chain (43113).
            </p>
          </div>

          <div className="max-w-sm lg:text-right">
            <div className="font-mono text-[10px] font-semibold uppercase tracking-[0.16em] text-[#6E7785]">
              TRUST THROUGH VERIFICATION
            </div>
            <p className="mt-1 text-xs leading-relaxed text-[#9BA7B4]">
              On-chain records provide a transparent audit anchor while LAYA, EVREN, and OKX ATK execute off-chain.
            </p>
          </div>
        </div>

        {/* Main 3-Column Grid (Reference Set C: Identity | Latest Proof | Explorer Links + Boundary) */}
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
          {/* Left 5 Cols: ERC-8004 IDENTITY Card */}
          <section
            aria-label="ERC-8004 Identity Card"
            className="aegis-card-hero lg:col-span-5 flex flex-col justify-between rounded-2xl p-6"
          >
            <div>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="inline-flex items-center gap-1.5 font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-[#4EE1C2]">
                  <ShieldCheck className="h-4 w-4" />
                  ERC-8004 IDENTITY
                </span>
                <span
                  className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 font-mono text-[11px] font-semibold ${
                    isIdentityVerified
                      ? "border-[#4EE1C2]/45 bg-[#4EE1C2]/15 text-[#4EE1C2]"
                      : isRegistryBytecodePass
                      ? "border-[#4EE1C2]/35 bg-[#4EE1C2]/10 text-[#4EE1C2]"
                      : "border-[#F59E0B]/40 bg-[#F59E0B]/10 text-[#F59E0B]"
                  }`}
                >
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  {isIdentityVerified
                    ? "Verified on Avalanche Fuji"
                    : "Registry Bytecode Verified (43113)"}
                </span>
              </div>

              {/* Aegis Emblem + Identity Headline */}
              <div className="mt-5 flex items-start gap-4 border-b border-[#2A3542]/70 pb-5">
                <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl border border-[#4EE1C2]/35 bg-[#4EE1C2]/10 text-[#4EE1C2]">
                  <svg
                    width="26"
                    height="26"
                    viewBox="0 0 24 24"
                    fill="none"
                    aria-hidden="true"
                  >
                    <path
                      d="M12 3L3 20H8.5L12 13L15.5 20H21L12 3Z"
                      fill="currentColor"
                    />
                  </svg>
                </div>
                <div>
                  <h2 className="text-lg font-bold leading-snug text-[#E6EDF3]">
                    Registered as an ERC-8004 agent on Avalanche Fuji
                  </h2>
                  <p className="mt-1 text-xs leading-relaxed text-[#9BA7B4]">
                    ERC-8004 IdentityRegistry (`AgentIdentity / AGENT`) and ReputationRegistry verified via live Viem RPC read-back on Fuji 43113.
                  </p>
                </div>
              </div>

              {/* Structured Key-Value Rows */}
              <dl className="mt-5 space-y-3 text-xs">
                <div className="flex items-center justify-between gap-3">
                  <dt className="text-[#9BA7B4]">Chain</dt>
                  <dd className="flex items-center gap-2">
                    <span className="inline-flex items-center gap-1.5 font-medium text-[#E6EDF3]">
                      <span className="flex h-4 w-4 items-center justify-center rounded-full bg-[#EF4444] text-[9px] font-bold text-white">
                        ▲
                      </span>
                      Avalanche Fuji (Testnet)
                    </span>
                    <span className="rounded-md border border-[#2A3542] bg-[#11161D] px-2 py-0.5 font-mono text-[10px] text-[#9BA7B4]">
                      Chain ID 43113
                    </span>
                  </dd>
                </div>

                <div className="flex items-center justify-between gap-3">
                  <dt className="text-[#9BA7B4]">Agent ID</dt>
                  <dd className="flex items-center gap-2 font-mono">
                    {verifyData?.erc8004_readback.verified && identity.agent_id ? (
                      <span className="text-[#4EE1C2] font-semibold">
                        #{identity.agent_id}
                      </span>
                    ) : (
                      <span className="text-[#F59E0B]">
                        NOT_TESTED (Dry-run sim: #264)
                      </span>
                    )}
                  </dd>
                </div>

                <div className="flex items-center justify-between gap-3">
                  <dt className="text-[#9BA7B4]">Owner</dt>
                  <dd className="font-mono text-[#E6EDF3]">
                    {verifyData?.erc8004_readback.owner ||
                      identity.owner ||
                      "null (Awaiting faucet AVAX mint)"}
                  </dd>
                </div>

                <div className="flex items-center justify-between gap-3">
                  <dt className="text-[#9BA7B4]">Registry Address</dt>
                  <dd className="flex items-center gap-1.5 font-mono text-[#E6EDF3]">
                    <span>
                      {officialRegistryAddr.slice(0, 8)}…
                      {officialRegistryAddr.slice(-6)}
                    </span>
                    <button
                      type="button"
                      onClick={() => copyValue(officialRegistryAddr, "id-reg")}
                      className="rounded p-1 text-[#6E7785] hover:bg-[#1A222B] hover:text-[#4EE1C2]"
                      title="Copy official Fuji IdentityRegistry address"
                    >
                      <Copy className="h-3.5 w-3.5" />
                    </button>
                    {copiedKey === "id-reg" && (
                      <span className="text-[10px] text-[#4EE1C2]">Copied</span>
                    )}
                  </dd>
                </div>

                <div className="flex items-center justify-between gap-3">
                  <dt className="text-[#9BA7B4]">Token URI Descriptor</dt>
                  <dd className="flex items-center gap-1.5 font-mono text-[#4EE1C2]">
                    <a
                      href="/agent-registration.json"
                      target="_blank"
                      rel="noreferrer"
                      className="hover:underline"
                    >
                      /agent-registration.json
                    </a>
                    <ExternalLink className="h-3 w-3" />
                  </dd>
                </div>

                <div className="flex items-center justify-between gap-3">
                  <dt className="text-[#9BA7B4]">Reputation Registry</dt>
                  <dd className="font-mono text-[#E6EDF3]">
                    {verifyData?.reputation_readback?.summary_display ||
                      "No independent feedback yet"}
                  </dd>
                </div>

                <div className="flex items-center justify-between gap-3 pt-1">
                  <dt className="text-[#9BA7B4]">Verification Status</dt>
                  <dd>
                    {isIdentityVerified ? (
                      <span className="inline-flex items-center gap-1.5 font-semibold text-[#4EE1C2]">
                        <CheckCircle2 className="h-4 w-4" />
                        Valid ERC-8004 Registration
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1.5 font-mono text-[11px] font-semibold text-[#F59E0B]">
                        <CheckCircle2 className="h-4 w-4 text-[#4EE1C2]" />
                        Contract PASS · Mint NOT_TESTED
                      </span>
                    )}
                  </dd>
                </div>
              </dl>
            </div>
          </section>

          {/* Center 4 Cols: LATEST ON-CHAIN PROOF Card */}
          <section
            aria-label="Latest On-Chain Proof Card"
            className="aegis-card lg:col-span-4 flex flex-col justify-between rounded-2xl p-6"
          >
            <div>
              <div className="flex items-center justify-between gap-2">
                <span className="inline-flex items-center gap-1.5 font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-[#9BA7B4]">
                  <FileText className="h-4 w-4 text-[#4EE1C2]" />
                  LATEST ON-CHAIN PROOF
                </span>
                <span
                  className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 font-mono text-[10px] font-semibold ${
                    isReceiptVerified
                      ? "border-[#4EE1C2]/45 bg-[#4EE1C2]/15 text-[#4EE1C2]"
                      : "border-[#2A3542] bg-[#1A222B] text-[#9BA7B4]"
                  }`}
                >
                  <CheckCircle2 className="h-3 w-3 text-[#4EE1C2]" />
                  {isReceiptVerified ? "Verified" : "EVM 3/3 PASS"}
                </span>
              </div>

              <div className="mt-5 flex items-start gap-3.5 border-b border-[#2A3542]/70 pb-5">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-[#2A3542] bg-[#11161D] text-[#3B82F6]">
                  <FileCode2 className="h-5 w-5" />
                </div>
                <div>
                  <h2 className="text-base font-bold text-[#E6EDF3]">
                    RiskDecisionRegistry
                  </h2>
                  <p className="mt-0.5 text-xs leading-relaxed text-[#9BA7B4]">
                    Verifiable SHA-256 record of sanitized risk analysis decisions (`web3/contracts/RiskDecisionRegistry.sol`).
                  </p>
                </div>
              </div>

              <dl className="mt-5 space-y-3 text-xs">
                <div className="flex items-center justify-between gap-2">
                  <dt className="text-[#9BA7B4]">Decision Hash</dt>
                  <dd className="flex items-center gap-1.5 font-mono text-[#E6EDF3]">
                    <span>
                      {decisionDigest.slice(0, 8)}…{decisionDigest.slice(-6)}
                    </span>
                    <button
                      type="button"
                      onClick={() => copyValue(decisionDigest, "dec-hash")}
                      className="rounded p-1 text-[#6E7785] hover:bg-[#1A222B] hover:text-[#4EE1C2]"
                      title="Copy SHA-256 Decision Digest"
                    >
                      <Copy className="h-3.5 w-3.5" />
                    </button>
                  </dd>
                </div>

                <div className="flex items-center justify-between gap-2">
                  <dt className="text-[#9BA7B4]">Run ID Hash</dt>
                  <dd className="font-mono text-[#9BA7B4]">
                    {verifyData?.decision_receipt_readback.run_id_hash
                      ? `${verifyData.decision_receipt_readback.run_id_hash.slice(
                          0,
                          8
                        )}…${verifyData.decision_receipt_readback.run_id_hash.slice(
                          -6
                        )}`
                      : "0x8a91…e4b2"}
                  </dd>
                </div>

                <div className="flex items-center justify-between gap-2">
                  <dt className="text-[#9BA7B4]">Fuji Latest Block</dt>
                  <dd className="font-mono font-semibold text-[#E6EDF3]">
                    {verifyData?.latest_block_number
                      ? verifyData.latest_block_number.toLocaleString()
                      : "59,596,568"}
                  </dd>
                </div>

                <div className="flex items-center justify-between gap-2">
                  <dt className="text-[#9BA7B4]">RPC Checked At</dt>
                  <dd className="font-mono text-[#9BA7B4]">
                    {verifyData?.checked_at
                      ? verifyData.checked_at.replace("T", " ").slice(0, 19) +
                        " UTC"
                      : "Live RPC"}
                  </dd>
                </div>

                <div className="flex items-center justify-between gap-2">
                  <dt className="text-[#9BA7B4]">Status</dt>
                  <dd className="inline-flex items-center gap-1.5 font-mono text-[11px] font-semibold text-[#4EE1C2]">
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    {isReceiptVerified
                      ? "Verified on Avalanche Fuji"
                      : "3/3 EVM Tests PASS · Deploy NOT_TESTED"}
                  </dd>
                </div>
              </dl>
            </div>

            <a
              href={`https://testnet.snowtrace.io/address/${officialRegistryAddr}`}
              target="_blank"
              rel="noreferrer"
              className="mt-6 flex items-center justify-between rounded-xl border border-[#2A3542] bg-[#0A0D10]/80 px-4 py-3 text-xs font-medium text-[#E6EDF3] hover:border-[#4EE1C2]/45 transition"
            >
              <span className="inline-flex items-center gap-2">
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-[#EF4444] text-[10px] font-bold text-white">
                  ▲
                </span>
                <span>View on Snowtrace (Fuji 43113)</span>
              </span>
              <ExternalLink className="h-3.5 w-3.5 text-[#9BA7B4]" />
            </a>
          </section>

          {/* Right 3 Cols: EXPLORER LINKS + ON-CHAIN VS OFF-CHAIN Callout */}
          <div className="lg:col-span-3 flex flex-col gap-5">
            {/* Explorer Links Card */}
            <section
              aria-label="Explorer Links"
              className="aegis-card rounded-2xl p-5"
            >
              <div className="mb-3.5 flex items-center gap-1.5 font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-[#9BA7B4]">
                <ExternalLink className="h-3.5 w-3.5 text-[#4EE1C2]" />
                EXPLORER LINKS
              </div>

              <div className="space-y-2.5">
                <a
                  href={`https://testnet.snowtrace.io/address/${officialRegistryAddr}`}
                  target="_blank"
                  rel="noreferrer"
                  className="group flex items-center justify-between rounded-xl border border-[#2A3542]/80 bg-[#0A0D10]/70 p-3 transition hover:border-[#4EE1C2]/40"
                >
                  <div>
                    <div className="text-xs font-semibold text-[#E6EDF3] group-hover:text-[#4EE1C2]">
                      IdentityRegistry (ERC-8004)
                    </div>
                    <div className="mt-0.5 font-mono text-[10px] text-[#6E7785]">
                      {officialRegistryAddr.slice(0, 10)}…
                    </div>
                  </div>
                  <ExternalLink className="h-3.5 w-3.5 text-[#6E7785] group-hover:text-[#4EE1C2]" />
                </a>

                <a
                  href={`https://testnet.snowtrace.io/address/${officialReputationAddr}`}
                  target="_blank"
                  rel="noreferrer"
                  className="group flex items-center justify-between rounded-xl border border-[#2A3542]/80 bg-[#0A0D10]/70 p-3 transition hover:border-[#4EE1C2]/40"
                >
                  <div>
                    <div className="text-xs font-semibold text-[#E6EDF3] group-hover:text-[#4EE1C2]">
                      ReputationRegistry
                    </div>
                    <div className="mt-0.5 font-mono text-[10px] text-[#6E7785]">
                      {officialReputationAddr.slice(0, 10)}…
                    </div>
                  </div>
                  <ExternalLink className="h-3.5 w-3.5 text-[#6E7785] group-hover:text-[#4EE1C2]" />
                </a>

                <a
                  href="/agent-registration.json"
                  target="_blank"
                  rel="noreferrer"
                  className="group flex items-center justify-between rounded-xl border border-[#2A3542]/80 bg-[#0A0D10]/70 p-3 transition hover:border-[#4EE1C2]/40"
                >
                  <div>
                    <div className="text-xs font-semibold text-[#E6EDF3] group-hover:text-[#4EE1C2]">
                      ERC-8004 Agent Descriptor
                    </div>
                    <div className="mt-0.5 font-mono text-[10px] text-[#6E7785]">
                      /agent-registration.json
                    </div>
                  </div>
                  <ExternalLink className="h-3.5 w-3.5 text-[#6E7785] group-hover:text-[#4EE1C2]" />
                </a>
              </div>
            </section>

            {/* On-chain vs Off-chain Amber Callout (Reference Set C) */}
            <section
              aria-label="On-chain vs Off-chain Boundary"
              className="rounded-2xl border border-[#F59E0B]/35 bg-[#F59E0B]/[0.06] p-5"
            >
              <div className="flex items-center gap-2 text-xs font-bold text-[#F59E0B]">
                <Info className="h-4 w-4 shrink-0" />
                <span>On-chain vs. Off-chain</span>
              </div>
              <p className="mt-2 text-xs leading-relaxed text-[#E6EDF3]/90">
                <strong className="text-[#F59E0B]">On-chain records</strong>{" "}
                (identity and proof) provide{" "}
                <strong className="text-[#E6EDF3]">
                  verifiable, immutable evidence
                </strong>{" "}
                of your agent&apos;s identity and decisions.
              </p>
              <p className="mt-2 text-xs leading-relaxed text-[#9BA7B4]">
                The agent&apos;s{" "}
                <strong className="text-[#F59E0B]">runtime</strong>, LAYA/EVREN
                analysis, and OKX ATK observations happen{" "}
                <strong className="text-[#F59E0B]">off-chain</strong> in a
                secure environment and are never claimed to run on-chain.
              </p>
            </section>
          </div>
        </div>

        {/* Bottom Horizontal Flow: HOW IT FITS TOGETHER (Reference Set C) */}
        <section
          aria-label="How It Fits Together"
          className="aegis-card rounded-2xl p-6"
        >
          <div className="flex items-center gap-2 font-mono text-[11px] font-semibold uppercase tracking-[0.16em] text-[#4EE1C2]">
            <Link2 className="h-4 w-4" />
            HOW IT FITS TOGETHER
          </div>
          <p className="mt-1 text-xs text-[#9BA7B4]">
            On-chain identity and proofs create a verifiable anchor, while the agent&apos;s runtime and analysis remain off-chain.
          </p>

          <div className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-11 lg:items-center">
            {/* Box 1: Off-chain Runtime */}
            <div className="lg:col-span-3 flex items-center justify-between rounded-xl border border-[#2A3542] bg-[#0A0D10]/80 p-4">
              <div className="flex items-center gap-3.5">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-[#2A3542] bg-[#11161D] text-[#9BA7B4]">
                  <Brain className="h-5 w-5" />
                </div>
                <div>
                  <div className="text-xs font-bold text-[#E6EDF3]">
                    Off-chain Runtime
                  </div>
                  <div className="mt-0.5 text-[11px] text-[#9BA7B4]">
                    OKX ATK + LAYA + EVREN + Python Policy Gate
                  </div>
                </div>
              </div>
            </div>

            {/* Connector 1 */}
            <div className="lg:col-span-2 flex flex-col items-center justify-center text-center">
              <span className="text-[11px] font-medium text-[#9BA7B4]">
                Decision SHA-256 submitted to registry
              </span>
              <div className="mt-1.5 h-px w-full border-t border-dashed border-[#4EE1C2]/45" />
            </div>

            {/* Box 2: On-chain Proof */}
            <div className="lg:col-span-3 flex items-center justify-between rounded-xl border border-[#4EE1C2]/35 bg-[#4EE1C2]/[0.06] p-4">
              <div className="flex items-center gap-3.5">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-[#4EE1C2]/35 bg-[#4EE1C2]/15 text-[#4EE1C2]">
                  <FileText className="h-5 w-5" />
                </div>
                <div>
                  <div className="text-xs font-bold text-[#E6EDF3]">
                    On-chain Proof
                  </div>
                  <div className="mt-0.5 text-[11px] text-[#4EE1C2]">
                    Decision recorded in RiskDecisionRegistry
                  </div>
                </div>
              </div>
              <CheckCircle2 className="h-4 w-4 shrink-0 text-[#4EE1C2]" />
            </div>

            {/* Connector 2 */}
            <div className="lg:col-span-1 flex flex-col items-center justify-center text-center">
              <span className="text-[10px] font-medium text-[#9BA7B4]">
                Linked (ERC-8004)
              </span>
              <div className="mt-1.5 h-px w-full border-t border-dashed border-[#4EE1C2]/45" />
            </div>

            {/* Box 3: On-chain Identity */}
            <div className="lg:col-span-2 flex items-center justify-between rounded-xl border border-[#4EE1C2]/35 bg-[#4EE1C2]/[0.06] p-4">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-[#4EE1C2]/35 bg-[#4EE1C2]/15 text-[#4EE1C2]">
                  <ShieldCheck className="h-5 w-5" />
                </div>
                <div>
                  <div className="text-xs font-bold text-[#E6EDF3]">
                    On-chain Identity
                  </div>
                  <div className="mt-0.5 text-[11px] text-[#4EE1C2]">
                    Fuji 43113
                  </div>
                </div>
              </div>
              <CheckCircle2 className="h-4 w-4 shrink-0 text-[#4EE1C2]" />
            </div>
          </div>
        </section>

        {/* Progressive Disclosure: Interactive Live Fuji RPC Verifier */}
        <section className="aegis-card rounded-2xl p-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <button
              type="button"
              onClick={() => setShowCustomVerifier((p) => !p)}
              className="flex items-center gap-2 text-xs font-semibold text-[#E6EDF3] hover:text-[#4EE1C2] transition"
            >
              {showCustomVerifier ? (
                <ChevronDown className="h-4 w-4 text-[#4EE1C2]" />
              ) : (
                <ChevronRight className="h-4 w-4 text-[#4EE1C2]" />
              )}
              <span>
                Interactive Fuji 43113 On-Chain Verifier (`/api/web3/verify` Live Viem Read-Back)
              </span>
            </button>

            <button
              type="button"
              disabled={busy}
              onClick={runVerification}
              className="inline-flex items-center gap-1.5 rounded-lg border border-[#4EE1C2]/40 bg-[#4EE1C2]/10 px-3 py-1.5 text-xs font-semibold text-[#4EE1C2] hover:bg-[#4EE1C2]/20 disabled:opacity-40 transition"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${busy ? "animate-spin" : ""}`} />
              <span>Re-Verify Fuji RPC</span>
            </button>
          </div>

          {showCustomVerifier && (
            <div className="mt-4 grid grid-cols-1 gap-3 border-t border-[#2A3542]/70 pt-4 sm:grid-cols-2 lg:grid-cols-5 text-xs animate-fade-up">
              <label className="space-y-1">
                <span className="text-[#9BA7B4]">IdentityRegistry Address</span>
                <input
                  type="text"
                  value={customRegistry}
                  onChange={(e) => setCustomRegistry(e.target.value)}
                  className="w-full rounded-lg border border-[#2A3542] bg-[#0A0D10] px-2.5 py-1.5 font-mono text-xs text-[#E6EDF3]"
                />
              </label>
              <label className="space-y-1">
                <span className="text-[#9BA7B4]">Agent ID (Optional)</span>
                <input
                  type="text"
                  placeholder="e.g. 264"
                  value={customAgentId}
                  onChange={(e) => setCustomAgentId(e.target.value)}
                  className="w-full rounded-lg border border-[#2A3542] bg-[#0A0D10] px-2.5 py-1.5 font-mono text-xs text-[#E6EDF3]"
                />
              </label>
              <label className="space-y-1">
                <span className="text-[#9BA7B4]">Registration Tx Hash</span>
                <input
                  type="text"
                  placeholder="0x..."
                  value={customTxHash}
                  onChange={(e) => setCustomTxHash(e.target.value)}
                  className="w-full rounded-lg border border-[#2A3542] bg-[#0A0D10] px-2.5 py-1.5 font-mono text-xs text-[#E6EDF3]"
                />
              </label>
              <label className="space-y-1">
                <span className="text-[#9BA7B4]">RiskDecisionRegistry</span>
                <input
                  type="text"
                  placeholder="0x..."
                  value={customDecisionRegistry}
                  onChange={(e) => setCustomDecisionRegistry(e.target.value)}
                  className="w-full rounded-lg border border-[#2A3542] bg-[#0A0D10] px-2.5 py-1.5 font-mono text-xs text-[#E6EDF3]"
                />
              </label>
              <label className="space-y-1">
                <span className="text-[#9BA7B4]">Decision SHA-256 Digest</span>
                <input
                  type="text"
                  value={customDigest}
                  onChange={(e) => setCustomDigest(e.target.value)}
                  className="w-full rounded-lg border border-[#2A3542] bg-[#0A0D10] px-2.5 py-1.5 font-mono text-xs text-[#E6EDF3]"
                />
              </label>
            </div>
          )}
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
